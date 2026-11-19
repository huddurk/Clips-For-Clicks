
import re
import subprocess
import uuid
from pathlib import Path

from flask import Flask, render_template, request, jsonify, send_from_directory
from faster_whisper import WhisperModel

BASE = Path(__file__).resolve().parent
UPLOADS = BASE / "uploads"
OUTPUTS = BASE / "outputs"

UPLOADS.mkdir(exist_ok=True)
OUTPUTS.mkdir(exist_ok=True)

app = Flask(__name__)
app.config["MAX_CONTENT_LENGTH"] = 2 * 1024 * 1024 * 1024

model = None

ALLOWED_DURATIONS = {15, 30, 45, 60}
ALLOWED_COUNTS = {3, 5, 10, 20}


def get_model():
    global model

    if model is None:
        model = WhisperModel(
            "small",
            device="cpu",
            compute_type="int8"
        )

    return model


def run(cmd):
    result = subprocess.run(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True
    )

    if result.returncode != 0:
        raise RuntimeError(
            result.stderr[-1800:] or "Media processing failed."
        )


def seconds(value):
    return max(0, float(value))


def score_segment(text):
    words = re.findall(r"[A-Za-z']+", text.lower())

    hooks = {
        "secret", "crazy", "insane", "never", "best",
        "worst", "amazing", "unbelievable", "mistake",
        "truth", "actually", "why", "how", "first",
        "finally"
    }

    score = min(len(words), 28) / 8
    score += sum(1.3 for word in words if word in hooks)

    if "?" in text or "!" in text:
        score += 1.0

    return score


def format_srt_time(value):
    millis_total = max(0, round(value * 1000))

    hours = millis_total // 3600000
    minutes = (millis_total % 3600000) // 60000
    seconds_part = (millis_total % 60000) // 1000
    millis = millis_total % 1000

    return (
        f"{hours:02}:{minutes:02}:"
        f"{seconds_part:02},{millis:03}"
    )


def get_video_duration(filename):
    result = subprocess.run(
        [
            "ffprobe",
            "-v", "error",
            "-show_entries", "format=duration",
            "-of", "default=noprint_wrappers=1:nokey=1",
            str(filename)
        ],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True
    )

    if result.returncode != 0:
        raise RuntimeError("Could not read the video duration.")

    return float(result.stdout.strip())


def make_candidates(transcript, video_duration, clip_duration):
    candidates = []

    actual_duration = min(clip_duration, video_duration)

    if actual_duration <= 0:
        return []

    for segment in transcript:
        center = (
            seconds(segment.start) +
            seconds(segment.end)
        ) / 2

        start = max(0, center - actual_duration / 2)
        start = min(
            start,
            max(0, video_duration - actual_duration)
        )

        end = min(video_duration, start + actual_duration)

        parts = [
            segment.text.strip()
            for segment in transcript
            if seconds(segment.end) > start
            and seconds(segment.start) < end
        ]

        phrase = " ".join(parts).strip()

        if not phrase:
            continue

        score = score_segment(phrase)

        candidates.append({
            "score": score,
            "start": start,
            "end": end,
            "caption": phrase
        })

    candidates.sort(
        key=lambda candidate: candidate["score"],
        reverse=True
    )

    # Avoid selecting clips that overlap heavily.
    selected = []

    for candidate in candidates:
        overlaps = False

        for existing in selected:
            overlap = max(
                0,
                min(candidate["end"], existing["end"]) -
                max(candidate["start"], existing["start"])
            )

            shorter = min(
                candidate["end"] - candidate["start"],
                existing["end"] - existing["start"]
            )

            if shorter > 0 and overlap / shorter > 0.5:
                overlaps = True
                break

        if not overlaps:
            selected.append(candidate)

    selected.sort(key=lambda candidate: candidate["start"])

    return selected


def make_srt(transcript, start, end, output_file):
    entries = []

    for segment in transcript:
        segment_start = max(seconds(segment.start), start)
        segment_end = min(seconds(segment.end), end)

        text = segment.text.strip()

        if segment_end <= segment_start or not text:
            continue

        relative_start = segment_start - start
        relative_end = segment_end - start

        entries.append(
            (relative_start, relative_end, text)
        )

    with open(output_file, "w", encoding="utf-8") as file:
        for number, (begin, finish, text) in enumerate(entries, 1):
            file.write(f"{number}\n")
            file.write(
                f"{format_srt_time(begin)} --> "
                f"{format_srt_time(finish)}\n"
            )
            file.write(f"{text}\n\n")


@app.get("/")
def home():
    return render_template("index.html")


@app.post("/api/clip")
def make_clips():
    if "video" not in request.files:
        return jsonify(error="Choose a video file first."), 400

    video = request.files["video"]

    if not video.filename:
        return jsonify(error="Choose a video file first."), 400

    # Validate settings sent by the website.
    try:
        clip_duration = int(request.form.get("clip_duration", 30))
        clip_count = int(request.form.get("clip_count", 5))
    except ValueError:
        return jsonify(error="Invalid clip settings."), 400

    if clip_duration not in ALLOWED_DURATIONS:
        return jsonify(error="Choose a valid clip length."), 400

    if clip_count not in ALLOWED_COUNTS:
        return jsonify(error="Choose a valid number of clips."), 400

    captions_enabled = (
        request.form.get("captions", "true").lower() == "true"
    )

    # Use a generated filename rather than trusting the uploaded filename.
    job = uuid.uuid4().hex[:12]
    source = UPLOADS / f"{job}_source"
    saved_subtitles = []

    try:
        video.save(source)

        video_duration = get_video_duration(source)

        if video_duration <= 0:
            return jsonify(error="This video has an invalid duration."), 400

        transcriber = get_model()

        segments, info = transcriber.transcribe(
            str(source),
            vad_filter=True,
            word_timestamps=False
        )

        transcript = list(segments)

        if not transcript:
            return jsonify(
                error="No speech was detected. Try a video with clear spoken audio."
            ), 422

        candidates = make_candidates(
            transcript,
            video_duration,
            clip_duration
        )

        if not candidates:
            return jsonify(
                error="Could not find suitable moments in this video."
            ), 422

        chosen = candidates[:clip_count]
        made = []

        for number, candidate in enumerate(chosen, 1):
            start = candidate["start"]
            end = candidate["end"]
            duration = end - start

            output = OUTPUTS / f"{job}_clip_{number}.mp4"

            video_filter = (
                "scale=1080:1920:"
                "force_original_aspect_ratio=increase,"
                "crop=1080:1920"
            )

            command = [
                "ffmpeg",
                "-y",
                "-ss", str(start),
                "-i", str(source),
                "-t", str(duration),
                "-map", "0:v:0",
                "-map", "0:a?",
                "-vf", video_filter,
            ]

            if captions_enabled:
                subtitle_file = OUTPUTS / f"{job}_clip_{number}.srt"

                make_srt(
                    transcript,
                    start,
                    end,
                    subtitle_file
                )

                saved_subtitles.append(subtitle_file)

                # The generated path contains only safe characters.
                subtitle_filter = (
                    f"subtitles=filename={subtitle_file}:"
                    "force_style='FontName=Arial,"
                    "FontSize=18,Outline=2,"
                    "Alignment=2,MarginV=100'"
                )

                command.extend([
                    "-vf",
                    video_filter + "," + subtitle_filter
                ])

            command.extend([
                "-c:v", "libx264",
                "-preset", "veryfast",
                "-crf", "23",
                "-c:a", "aac",
                "-b:a", "128k",
                "-movflags", "+faststart",
                str(output)
            ])

            run(command)

            made.append({
                "name": f"Clip {number}",
                "file": output.name,
                "start": round(start, 1),
                "duration": round(duration, 1),
                "caption": candidate["caption"][:180]
            })

        return jsonify(
            clips=made,
            note=(
                "Clips were ranked using transcript-based highlight scoring. "
                "Review each clip before sharing."
            )
        )

    except Exception as error:
        app.logger.exception("Clip processing failed")
        return jsonify(error=str(error)), 500

    finally:
        try:
            source.unlink(missing_ok=True)
        except Exception:
            pass

        for subtitle_file in saved_subtitles:
            try:
                subtitle_file.unlink(missing_ok=True)
            except Exception:
                pass


@app.get("/outputs/<path:filename>")
def output_file(filename):
    return send_from_directory(
        OUTPUTS,
        filename,
        as_attachment=True
    )


if __name__ == "__main__":
    app.run(
        host="0.0.0.0",
        port=5000,
        debug=False
    )

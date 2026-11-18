import os, re, subprocess, uuid, json
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

def get_model():
    global model
    if model is None:
        # Downloads the small speech model the first time the app is used.
        model = WhisperModel("small", device="cpu", compute_type="int8")
    return model

def run(cmd):
    p = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    if p.returncode:
        raise RuntimeError(p.stderr[-1800:] or "Media processing failed.")

def seconds(t):
    return max(0, float(t))

def score_segment(text):
    words = re.findall(r"[A-Za-z']+", text.lower())
    hooks = {"secret", "crazy", "insane", "never", "best", "worst", "amazing",
             "unbelievable", "mistake", "truth", "actually", "why", "how",
             "first", "finally", "爆"}
    score = min(len(words), 28) / 8
    score += sum(1.3 for w in words if w in hooks)
    score += 1.0 if "?" in text or "!" in text else 0
    return score

@app.get("/")
def home():
    return render_template("index.html")

@app.post("/api/clip")
def make_clips():
    if "video" not in request.files:
        return jsonify(error="Choose a video first."), 400
    video = request.files["video"]
    if not video.filename:
        return jsonify(error="Choose a video first."), 400

    job = uuid.uuid4().hex[:10]
    source = UPLOADS / f"{job}_{Path(video.filename).name}"
    video.save(source)
    try:
        transcriber = get_model()
        segments, info = transcriber.transcribe(str(source), vad_filter=True, word_timestamps=False)
        transcript = list(segments)
        if not transcript:
            return jsonify(error="No speech was detected. Try a video with clear spoken audio."), 422

        # Group adjacent transcript segments into candidate moments of roughly 20–55 seconds.
        candidates = []
        i = 0
        while i < len(transcript):
            start = seconds(transcript[i].start)
            end = start
            parts = []
            while i < len(transcript) and end - start < 48:
                parts.append(transcript[i].text.strip())
                end = seconds(transcript[i].end)
                i += 1
                if end - start >= 20:
                    break
            phrase = " ".join(parts).strip()
            if end - start >= 12 and phrase:
                candidates.append((score_segment(phrase), start, end, phrase))

        if not candidates:
            first, last = transcript[0], transcript[-1]
            candidates = [(1, seconds(first.start), seconds(last.end),
                           " ".join(s.text.strip() for s in transcript))]

        candidates.sort(key=lambda x: x[0], reverse=True)
        made = []
        for n, (_, start, end, phrase) in enumerate(candidates[:5], 1):
            out = OUTPUTS / f"{job}_clip_{n}.mp4"
            duration = max(1, end - start)
            # Crop to a vertical 9:16 frame, scale to fit, and add a simple title-safe layout.
            vf = "scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920"
            run(["ffmpeg", "-y", "-ss", str(start), "-i", str(source), "-t", str(duration),
                 "-vf", vf, "-c:v", "libx264", "-preset", "veryfast", "-crf", "23",
                 "-c:a", "aac", "-b:a", "128k", "-movflags", "+faststart", str(out)])
            made.append({"name": f"Clip {n}", "file": out.name,
                         "start": round(start, 1), "duration": round(duration, 1),
                         "caption": phrase[:180]})
        return jsonify(clips=made, note="AI-selected moments are ranked using the spoken transcript. Review clips before posting.")
    except Exception as e:
        return jsonify(error=str(e)), 500
    finally:
        try: source.unlink(missing_ok=True)
        except Exception: pass

@app.get("/outputs/<path:filename>")
def output_file(filename):
    return send_from_directory(OUTPUTS, filename, as_attachment=True)

if __name__ == "__main__":
    app.run(host="127.0.0.1", port=5000, debug=False)

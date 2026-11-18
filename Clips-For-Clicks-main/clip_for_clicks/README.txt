CLIP FOR CLICKS — LOCAL AI CLIPPING WEBSITE

What this starter does:
- Runs a website on your computer.
- Lets you upload a video file.
- Uses Faster-Whisper to transcribe spoken audio.
- Ranks transcript moments and exports up to five vertical 9:16 clips.
- Lets you download each clip.

IMPORTANT:
This is a working local starter, not a publicly hosted website. It does not yet add animated word-by-word captions, face tracking, or cloud accounts. Highlight ranking is a basic transcript-based heuristic, so review clips before posting.

SETUP (Windows):
1. Install Python 3.10 or newer.
2. Install FFmpeg and make sure the `ffmpeg` command works in Command Prompt.
   FFmpeg download: https://ffmpeg.org/download.html
3. Extract this ZIP.
4. Open the extracted folder in Command Prompt.
5. Run:
      py -m venv .venv
      .venv\Scripts\activate
      pip install -r requirements.txt
      py app.py
6. Open this address in your browser:
      http://127.0.0.1:5000

The first AI run downloads a speech model and can take a while. Processing speed depends on your computer.
Videos are processed locally; uploaded files are removed after processing. Generated clips stay in the outputs folder.

To publish this publicly, the app needs cloud hosting with FFmpeg, model storage, upload limits, and background job handling. Free hosting may sleep or have processing limits.


DEPLOYING ONLINE (Render):
1. You need a GitHub account and a Render account. Follow each site's age and account rules; ask a parent/guardian to help if needed.
2. Create a new GitHub repository and upload the contents of this folder (not the ZIP file itself).
3. In Render, choose New > Web Service and connect that GitHub repository.
4. Select Docker as the runtime. The included Dockerfile installs FFmpeg and the Python dependencies.
5. Deploy. The first AI request downloads the Whisper model and can take several minutes.
6. Once Render reports the service is live, open the URL it provides.

Hosting note:
This is a compute-heavy video-processing app. Free web hosting may sleep, time out, or lack enough memory/CPU for video jobs. The included Render configuration uses a paid Starter service as a more realistic baseline. Review current provider pricing before deploying. Do not upload private videos unless you are comfortable with the hosting provider processing them.

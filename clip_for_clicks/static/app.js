const input = document.getElementById('video');
const zone = document.getElementById('dropzone');
const title = document.getElementById('fileTitle');
const hint = document.getElementById('fileHint');
const form = document.getElementById('clipForm');
const btn = document.getElementById('submitBtn');
const progress = document.getElementById('progressWrap');
const status = document.getElementById('status');
const errorBox = document.getElementById('error');
const results = document.getElementById('results');

const videoUrl = document.getElementById('videoUrl');
const clipDuration = document.getElementById('clipDuration');
const clipCount = document.getElementById('clipCount');
const captions = document.getElementById('captions');

input.addEventListener('change', () => {
  if (input.files[0]) {
    title.textContent = input.files[0].name;
    hint.textContent =
      (input.files[0].size / 1024 / 1024).toFixed(1) +
      ' MB · Ready to clip';
    videoUrl.value = '';
  }
});

['dragenter', 'dragover'].forEach(eventName => {
  zone.addEventListener(eventName, event => {
    event.preventDefault();
    zone.classList.add('over');
  });
});

['dragleave', 'drop'].forEach(eventName => {
  zone.addEventListener(eventName, event => {
    event.preventDefault();
    zone.classList.remove('over');
  });
});

zone.addEventListener('drop', event => {
  if (event.dataTransfer.files.length) {
    input.files = event.dataTransfer.files;
    input.dispatchEvent(new Event('change'));
  }
});

videoUrl.addEventListener('input', () => {
  if (videoUrl.value.trim()) {
    input.value = '';
    title.textContent = 'Video link selected';
    hint.textContent = 'The link will be checked by the server';
  } else {
    title.textContent = 'Drag your video here';
    hint.innerHTML = 'or <u>browse files</u> from your device';
  }
});

form.addEventListener('submit', async event => {
  event.preventDefault();

  errorBox.hidden = true;
  results.hidden = true;

  const hasFile = input.files.length > 0;
  const hasUrl = videoUrl.value.trim().length > 0;

  if (!hasFile && !hasUrl) {
    errorBox.textContent = 'Upload a video file first.';
    errorBox.hidden = false;
    return;
  }

  if (hasUrl) {
    errorBox.textContent =
      'Video-link processing is not connected yet. For now, upload a video file you own or have permission to use.';
    errorBox.hidden = false;
    return;
  }

  const data = new FormData();

  data.append('video', input.files[0]);
  data.append('clip_duration', clipDuration.value);
  data.append('clip_count', clipCount.value);
  data.append('captions', captions.checked ? 'true' : 'false');

  btn.disabled = true;
  progress.hidden = false;
  status.textContent = 'Transcribing audio and finding highlights…';

  try {
    const response = await fetch('/api/clip', {
      method: 'POST',
      body: data
    });

    const payload = await response.json();

    if (!response.ok) {
      throw new Error(payload.error || 'Something went wrong.');
    }

    const list = document.getElementById('clipList');
    list.innerHTML = '';

    payload.clips.forEach((clip, index) => {
      const element = document.createElement('article');
      element.className = 'clip';

      const number = document.createElement('div');
      number.className = 'clip-number';
      number.textContent = String(index + 1).padStart(2, '0');

      const info = document.createElement('div');
      info.className = 'clip-info';

      const name = document.createElement('b');
      name.textContent = clip.name + ' · ' + clip.duration + ' sec';

      const description = document.createElement('p');
      description.textContent = clip.caption || '';

      info.append(name, description);

      const link = document.createElement('a');
      link.className = 'download';
      link.href = '/outputs/' + encodeURIComponent(clip.file);
      link.textContent = '↓ Download';

      element.append(number, info, link);
      list.append(element);
    });

    document.getElementById('resultCount').textContent =
      payload.clips.length + ' clips';

    results.hidden = false;
    status.textContent = 'Finished!';

  } catch (error) {
    errorBox.textContent = error.message;
    errorBox.hidden = false;
  } finally {
    btn.disabled = false;
    progress.hidden = true;
  }
});

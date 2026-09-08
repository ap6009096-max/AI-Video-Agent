# AI Creator Platform

## Deployment Workflow

The supported release path is:

```text
GitHub push -> Streamlit Community Cloud rebuild -> smoke test -> fix -> push again
```

The repository contains application code and configuration defaults only. API keys, cookies, and other credentials must remain in local `.env` files or Streamlit Community Cloud Secrets.

## Local Development

1. Create a virtual environment and install `requirements.txt`.
2. Copy `.env.example` to `.env`.
3. Set `GEMINI_API_KEY` in `.env` without committing the file.
4. For local development, install FFmpeg or set `FFMPEG_PATH`; deployments use the bundled `imageio-ffmpeg` executable.
5. Start the app with `streamlit run app.py`.
6. Run `python -m pytest -q` before pushing.

The settings loader uses environment variables and `.env` locally. On Streamlit Community Cloud it falls back to `st.secrets` for `GEMINI_API_KEY`. CLI and tests continue to work when Streamlit is unavailable.

## Streamlit Community Cloud

Streamlit Community Cloud installs Python dependencies from `requirements.txt`.
This repository uses `imageio-ffmpeg` to provide the FFmpeg executable, so no
apt package file is required. The `Dockerfile` remains available for Docker
deployments and installs system FFmpeg there.

Configure the deployment Secrets with values such as:

```toml
GEMINI_API_KEY = "replace-with-a-secret-value"
YOUTUBE_DOWNLOAD_ENABLED = "true"
YOUTUBE_DOWNLOAD_FORMAT = "best[height<=720]/best"
YOUTUBE_COOKIES_FILE = ""
FFMPEG_PATH = ""
```

Never commit the actual values. `.env` and `.streamlit/secrets.toml` are ignored by Git. Do not upload personal YouTube cookies unless the use is authorized and the security implications are understood. After changing Secrets, allow Streamlit to complete a clean rebuild before testing a download.

## YouTube Downloads

YouTube downloads are intended for public or otherwise authorized media only. The application uses `yt-dlp` and requires FFmpeg for media processing and any stream merging.

The default format is the conservative single-stream request:

```text
best[height<=720]/best
```

If an older local configuration requests separate video and audio streams and that request fails, the downloader retries with the single-stream format. A 403 can still mean that YouTube rejected the media request, the video is restricted, or the downloader needs an update. Update `yt-dlp` before further diagnosis:

```bash
python -m pip install -U yt-dlp
python -m yt_dlp --version
python -c "import imageio_ffmpeg; print(imageio_ffmpeg.get_ffmpeg_exe())"
```

For an authorized public URL, test the downloader outside the application:

```bash
python -m yt_dlp --verbose --format "best[height<=720]/best" "YOUTUBE_URL"
```

If the request still returns 403, use direct video-file upload or resolve the access issue with the content owner. Do not attempt to bypass access controls.

## Output Durations

Multi Shorts Export defaults to four output durations:

- 30 seconds
- 1 minute
- 90 seconds
- 3 minutes

Rendered files are written under the project output directory, including `renders/shorts/`, `exports/`, and the final package locations.

## Release Checklist

- Run `python -m pytest -q`.
- Confirm `GEMINI_API_KEY` is configured only in local `.env` or deployment Secrets.
- Confirm no credentials appear in `git diff` or tracked files.
- Confirm FFmpeg is available in the deployment environment.
- Confirm `yt-dlp` is current when YouTube downloads are enabled.
- Push to the connected GitHub branch.
- Wait for Streamlit Community Cloud to rebuild, then test a script/upload workflow and an authorized YouTube URL if one is available.
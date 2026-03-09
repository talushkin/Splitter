# Splitter

Lightweight Python karaoke splitter — give it a YouTube video ID (or URL),
and it downloads the audio then separates it into **vocals** and
**accompaniment** MP3 files named after the video ID.

## Requirements

* Python 3.9+
* [ffmpeg](https://ffmpeg.org/) installed and on `PATH` (required by pydub)
* Python packages — install with:

```
pip install -r requirements.txt
# For running tests:
pip install -r requirements-dev.txt
```

## Usage

```python
from splitter import process_video

result = process_video("dQw4w9WgXcQ", output_dir="./out")
# or with a full URL:
result = process_video("https://www.youtube.com/watch?v=dQw4w9WgXcQ", "./out")

print(result["vocals"])          # ./out/dQw4w9WgXcQ_vocals.mp3
print(result["accompaniment"])   # ./out/dQw4w9WgXcQ_accompaniment.mp3
```

Individual functions are also importable:

| Function | Description |
|---|---|
| `extract_video_id(url_or_id)` | Parse an 11-char video ID from a URL or bare ID |
| `download_audio(video_id, output_dir)` | Download audio as MP3 via yt-dlp |
| `split_karaoke(audio_path, output_dir)` | Split MP3 into vocals + accompaniment |
| `process_video(url_or_id, output_dir)` | End-to-end pipeline |

## Tests

```
pytest test_splitter.py -v
```

All unit tests use mocks — no network access or audio files required.

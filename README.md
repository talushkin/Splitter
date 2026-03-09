# Splitter

Simple Flask app that:

- Accepts a YouTube URL or video ID from a small frontend form.
- Downloads the source audio as MP3.
- Splits vocals/instrumental (karaoke) with Spleeter.
- Saves the karaoke MP3 by video ID.
- Exposes an endpoint so other apps can request the MP3 by video ID.

## Requirements

- Python 3.10+
- `ffmpeg` installed on the system
- `spleeter` command available

Install Ubuntu packages:

```bash
sudo apt update
sudo apt install -y ffmpeg
```

Install Python dependencies:

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
pip install spleeter
```

If `pip install spleeter` fails in your default environment (common on Python 3.12),
you can use a dedicated conda environment and this app will auto-detect it:

```bash
/opt/conda/bin/conda create -y -n splitter-spleeter -c conda-forge python=3.10
/opt/conda/envs/splitter-spleeter/bin/python -m pip install --upgrade pip
/opt/conda/envs/splitter-spleeter/bin/python -m pip install spleeter
```

## Run

```bash
python app.py
```

Open `http://localhost:5000`.

## API

### `POST /api/process`

Body:

```json
{
	"video": "https://www.youtube.com/watch?v=dQw4w9WgXcQ"
}
```

Response:

```json
{
	"video_id": "dQw4w9WgXcQ",
	"status": "ready",
	"karaoke_url": "/api/karaoke/dQw4w9WgXcQ"
}
```

### `GET /api/karaoke/<video_id>`

Downloads the generated karaoke MP3 file.

### `GET /api/status/<video_id>`

Checks if karaoke MP3 is already available.

## Storage

Generated files are saved under `storage/`:

- `storage/downloads/<video_id>.mp3`
- `storage/stems/<video_id>/...`
- `storage/karaoke/<video_id>.mp3`

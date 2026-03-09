from __future__ import annotations

import json
import shutil
import subprocess
import sys
import time
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from flask import Flask, jsonify, render_template, request, send_file

BASE_DIR = Path(__file__).resolve().parent
STORAGE_DIR = BASE_DIR / "storage"
DOWNLOADS_DIR = STORAGE_DIR / "downloads"
STEMS_DIR = STORAGE_DIR / "stems"
KARAOKE_DIR = STORAGE_DIR / "karaoke"
CONDA_SPLEETER_BIN = Path("/opt/conda/envs/splitter-spleeter/bin/spleeter")

for folder in (DOWNLOADS_DIR, STEMS_DIR, KARAOKE_DIR):
    folder.mkdir(parents=True, exist_ok=True)

app = Flask(__name__)


def extract_video_id(value: str | None) -> str | None:
    if not value:
        return None

    value = value.strip()
    if len(value) == 11 and all(ch.isalnum() or ch in "-_" for ch in value):
        return value

    parsed = urlparse(value)
    host = parsed.netloc.lower()

    if host in {"youtu.be", "www.youtu.be"}:
        candidate = parsed.path.strip("/")
        if len(candidate) == 11:
            return candidate

    if host.endswith("youtube.com"):
        if parsed.path == "/watch":
            video_id = parse_qs(parsed.query).get("v", [None])[0]
            if video_id and len(video_id) == 11:
                return video_id

        if parsed.path.startswith("/shorts/"):
            candidate = parsed.path.split("/", 3)[2]
            if len(candidate) == 11:
                return candidate

    return None


def run_command(command: list[str]) -> None:
    result = subprocess.run(command, capture_output=True, text=True)
    if result.returncode != 0:
        stderr = result.stderr.strip() or "Unknown command error"
        raise RuntimeError(stderr)


def run_command_with_progress(
    command: list[str],
    *,
    label: str,
    expected_seconds: int = 240,
    step_percent: int = 5,
) -> None:
    """Run a command and emit progress checkpoints every `step_percent` based on elapsed time.

    The reported percentage is an elapsed-time estimate (capped at 95%) until the command exits,
    then 100% is logged with the final duration.
    """
    started_at = time.monotonic()
    next_checkpoint = step_percent
    app.logger.info("%s progress 0%% (0.0s elapsed)", label)

    process = subprocess.Popen(
        command,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )

    while process.poll() is None:
        elapsed = time.monotonic() - started_at
        estimated_percent = min(95, int((elapsed / max(expected_seconds, 1)) * 100))

        while next_checkpoint <= estimated_percent:
            app.logger.info(
                "%s progress %d%% (%.1fs elapsed)",
                label,
                next_checkpoint,
                elapsed,
            )
            next_checkpoint += step_percent

        time.sleep(1)

    stdout, stderr = process.communicate()
    elapsed = time.monotonic() - started_at
    app.logger.info("%s progress 100%% (%.1fs elapsed)", label, elapsed)

    if process.returncode != 0:
        error_text = (stderr or stdout or "Unknown command error").strip()
        raise RuntimeError(error_text)


def resolve_spleeter_command() -> list[str]:
    """Return a runnable command prefix for spleeter in this environment."""
    cli_path = shutil.which("spleeter")
    if cli_path:
        return [cli_path]

    if CONDA_SPLEETER_BIN.exists():
        return [str(CONDA_SPLEETER_BIN)]

    try:
        import spleeter  # noqa: F401
    except ImportError as exc:
        raise RuntimeError(
            "Spleeter is not installed in the current Python runtime. "
            "Install it in this environment, or provide a Spleeter CLI on PATH "
            "(for this container, /opt/conda/envs/splitter-spleeter/bin/spleeter is supported)."
        ) from exc

    return [sys.executable, "-m", "spleeter"]


def download_audio_mp3(video_id: str) -> Path:
    output_file = DOWNLOADS_DIR / f"{video_id}.mp3"
    if output_file.exists():
        return output_file

    try:
        import yt_dlp
    except ImportError as exc:
        raise RuntimeError("yt-dlp is not installed") from exc

    ydl_options = {
        "format": "bestaudio/best",
        "outtmpl": str(DOWNLOADS_DIR / f"{video_id}.%(ext)s"),
        "noplaylist": True,
        "quiet": True,
        "postprocessors": [
            {
                "key": "FFmpegExtractAudio",
                "preferredcodec": "mp3",
                "preferredquality": "192",
            }
        ],
    }

    url = f"https://www.youtube.com/watch?v={video_id}"
    with yt_dlp.YoutubeDL(ydl_options) as ydl:
        ydl.download([url])

    if not output_file.exists():
        raise RuntimeError("Audio download finished, but MP3 file was not created")

    return output_file


def build_karaoke_mp3(video_id: str, source_mp3: Path) -> Path:
    target_file = KARAOKE_DIR / f"{video_id}.mp3"
    if target_file.exists():
        return target_file

    stem_output_root = STEMS_DIR / video_id
    stem_output_root.mkdir(parents=True, exist_ok=True)

    # Separate vocals and accompaniment with Spleeter (2 stems).
    run_command_with_progress([
        *resolve_spleeter_command(),
        "separate",
        "-p",
        "spleeter:2stems",
        "-o",
        str(stem_output_root),
        str(source_mp3),
    ], label=f"split:{video_id}")

    accompaniment_wav = stem_output_root / source_mp3.stem / "accompaniment.wav"
    if not accompaniment_wav.exists():
        raise RuntimeError("Spleeter completed, but accompaniment stem was not found")

    # Convert accompaniment WAV to MP3 for lightweight sharing.
    run_command([
        "ffmpeg",
        "-y",
        "-i",
        str(accompaniment_wav),
        "-codec:a",
        "libmp3lame",
        "-q:a",
        "2",
        str(target_file),
    ])

    metadata_path = KARAOKE_DIR / f"{video_id}.json"
    metadata_path.write_text(
        json.dumps(
            {
                "video_id": video_id,
                "source_mp3": str(source_mp3.relative_to(BASE_DIR)),
                "karaoke_mp3": str(target_file.relative_to(BASE_DIR)),
            },
            indent=2,
        ),
        encoding="utf-8",
    )

    return target_file


@app.get("/")
def index() -> str:
    return render_template("index.html")


@app.get("/health")
def health():
    return jsonify({"status": "ok"})


@app.get("/api/status/<video_id>")
def status(video_id: str):
    if len(video_id) != 11:
        return jsonify({"error": "Invalid video ID"}), 400
    return jsonify(
        {
            "video_id": video_id,
            "available": (KARAOKE_DIR / f"{video_id}.mp3").exists(),
        }
    )


@app.post("/api/process")
def process_video():
    payload = request.get_json(silent=True) or request.form
    raw_video = payload.get("video") if payload else None
    video_id = extract_video_id(raw_video)

    if not video_id:
        return jsonify({"error": "Provide a valid YouTube URL or 11-char video ID"}), 400

    karaoke_file = KARAOKE_DIR / f"{video_id}.mp3"
    if karaoke_file.exists():
        return (
            jsonify(
                {
                    "video_id": video_id,
                    "status": "ready",
                    "karaoke_url": f"/api/karaoke/{video_id}",
                }
            ),
            200,
        )

    try:
        source_mp3 = download_audio_mp3(video_id)
        build_karaoke_mp3(video_id, source_mp3)
    except Exception as exc:  # noqa: BLE001
        return jsonify({"error": str(exc), "video_id": video_id}), 500

    return jsonify(
        {
            "video_id": video_id,
            "status": "ready",
            "karaoke_url": f"/api/karaoke/{video_id}",
        }
    )


@app.get("/api/karaoke/<video_id>")
def get_karaoke(video_id: str):
    karaoke_file = KARAOKE_DIR / f"{video_id}.mp3"
    if not karaoke_file.exists():
        return jsonify({"error": "Karaoke file not found for this video ID"}), 404

    return send_file(
        karaoke_file,
        mimetype="audio/mpeg",
        as_attachment=True,
        download_name=f"{video_id}_karaoke.mp3",
    )


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)

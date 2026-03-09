"""
Lightweight YouTube karaoke splitter.

Downloads audio from a YouTube video by video ID and separates it into
vocal and accompaniment (karaoke) tracks, saving each as an MP3 file
named after the video ID.
"""

import os
import re
import subprocess
from pathlib import Path

try:
    from pydub import AudioSegment
except ImportError:  # pragma: no cover
    AudioSegment = None  # type: ignore


# ---------------------------------------------------------------------------
# YouTube video ID helpers
# ---------------------------------------------------------------------------

_YT_ID_RE = re.compile(
    r"(?:youtube\.com/(?:watch\?v=|embed/|shorts/)|youtu\.be/)"
    r"([a-zA-Z0-9_-]{11})"
    r"|^([a-zA-Z0-9_-]{11})$"
)


def extract_video_id(url_or_id: str) -> str:
    """Return the 11-character YouTube video ID from a URL or bare ID.

    Args:
        url_or_id: A YouTube URL (youtube.com, youtu.be, embed, shorts)
            or a raw 11-character video ID.

    Returns:
        The 11-character video ID string.

    Raises:
        ValueError: When no valid video ID can be found.
    """
    match = _YT_ID_RE.search(url_or_id.strip())
    if match:
        return match.group(1) or match.group(2)
    raise ValueError(f"Cannot extract a YouTube video ID from: {url_or_id!r}")


# ---------------------------------------------------------------------------
# Audio download
# ---------------------------------------------------------------------------


def download_audio(video_id: str, output_dir: str = ".") -> str:
    """Download the audio track of a YouTube video as an MP3 file.

    Uses yt-dlp to extract and convert audio.  The resulting file is saved
    as ``<output_dir>/<video_id>.mp3``.

    Args:
        video_id: The 11-character YouTube video ID.
        output_dir: Directory where the MP3 will be saved.

    Returns:
        Path to the downloaded MP3 file (mirrors the structure of
        *output_dir*; will be absolute when *output_dir* is absolute).

    Raises:
        subprocess.CalledProcessError: When yt-dlp exits with a non-zero
            status (e.g. private/unavailable video).
    """
    os.makedirs(output_dir, exist_ok=True)
    output_template = os.path.join(output_dir, f"{video_id}.%(ext)s")
    cmd = [
        "yt-dlp",
        "--extract-audio",
        "--audio-format", "mp3",
        "--audio-quality", "0",
        "--output", output_template,
        f"https://www.youtube.com/watch?v={video_id}",
    ]
    subprocess.run(cmd, check=True)
    return os.path.join(output_dir, f"{video_id}.mp3")


# ---------------------------------------------------------------------------
# Karaoke splitting
# ---------------------------------------------------------------------------


def split_karaoke(audio_path: str, output_dir: str = ".") -> dict:
    """Split a stereo MP3 into vocal and accompaniment tracks.

    Uses a lightweight phase-cancellation technique:
    - *Accompaniment* (centre channel): average of left and right channels.
    - *Vocals*: the stereo difference (left – right).

    Both tracks are saved as ``<output_dir>/<video_id>_accompaniment.mp3``
    and ``<output_dir>/<video_id>_vocals.mp3``.

    Args:
        audio_path: Path to the source MP3 file.
        output_dir: Directory where the split MP3 files will be saved.

    Returns:
        A dict with keys ``"vocals"`` and ``"accompaniment"`` mapping to
        the absolute paths of the saved files.

    Raises:
        RuntimeError: When pydub is not installed.
        FileNotFoundError: When *audio_path* does not exist.
    """
    if AudioSegment is None:  # pragma: no cover
        raise RuntimeError("pydub is required: pip install pydub")

    audio_path = os.path.abspath(audio_path)
    if not os.path.isfile(audio_path):
        raise FileNotFoundError(f"Audio file not found: {audio_path}")

    os.makedirs(output_dir, exist_ok=True)

    video_id = Path(audio_path).stem
    audio = AudioSegment.from_mp3(audio_path)

    # Ensure stereo
    if audio.channels == 1:
        audio = audio.set_channels(2)

    left, right = audio.split_to_mono()

    # Accompaniment ≈ centre channel (sum / 2 keeps the same dBFS)
    accompaniment = left.overlay(right)

    # Vocals ≈ stereo difference; invert right channel, then overlay
    right_inverted = right.invert_phase()
    vocals = left.overlay(right_inverted)

    vocals_path = os.path.join(output_dir, f"{video_id}_vocals.mp3")
    accompaniment_path = os.path.join(output_dir, f"{video_id}_accompaniment.mp3")

    vocals.export(vocals_path, format="mp3")
    accompaniment.export(accompaniment_path, format="mp3")

    return {"vocals": vocals_path, "accompaniment": accompaniment_path}


# ---------------------------------------------------------------------------
# End-to-end pipeline
# ---------------------------------------------------------------------------


def process_video(video_id_or_url: str, output_dir: str = ".") -> dict:
    """Download and karaoke-split a YouTube video.

    Convenience wrapper that calls :func:`extract_video_id`,
    :func:`download_audio`, and :func:`split_karaoke` in sequence.

    Args:
        video_id_or_url: A YouTube URL or raw 11-character video ID.
        output_dir: Directory where all output files will be saved.

    Returns:
        A dict with keys ``"video_id"``, ``"source_mp3"``, ``"vocals"``,
        and ``"accompaniment"``.
    """
    video_id = extract_video_id(video_id_or_url)
    source_mp3 = download_audio(video_id, output_dir)
    tracks = split_karaoke(source_mp3, output_dir)
    return {
        "video_id": video_id,
        "source_mp3": source_mp3,
        **tracks,
    }

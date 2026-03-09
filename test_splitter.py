"""
Unit tests for splitter.py.

All tests use mocks so no network access or audio files are required.
"""

import os
import unittest
from unittest.mock import MagicMock, call, patch

import splitter
from splitter import (
    download_audio,
    extract_video_id,
    process_video,
    split_karaoke,
)


# ---------------------------------------------------------------------------
# extract_video_id
# ---------------------------------------------------------------------------


class TestExtractVideoId(unittest.TestCase):
    """Tests for extract_video_id()."""

    def test_bare_id_returned_unchanged(self):
        self.assertEqual(extract_video_id("dQw4w9WgXcQ"), "dQw4w9WgXcQ")

    def test_watch_url(self):
        self.assertEqual(
            extract_video_id("https://www.youtube.com/watch?v=dQw4w9WgXcQ"),
            "dQw4w9WgXcQ",
        )

    def test_watch_url_with_extra_params(self):
        self.assertEqual(
            extract_video_id(
                "https://www.youtube.com/watch?v=dQw4w9WgXcQ&list=PL1234"
            ),
            "dQw4w9WgXcQ",
        )

    def test_short_url(self):
        self.assertEqual(
            extract_video_id("https://youtu.be/dQw4w9WgXcQ"), "dQw4w9WgXcQ"
        )

    def test_embed_url(self):
        self.assertEqual(
            extract_video_id("https://www.youtube.com/embed/dQw4w9WgXcQ"),
            "dQw4w9WgXcQ",
        )

    def test_shorts_url(self):
        self.assertEqual(
            extract_video_id("https://www.youtube.com/shorts/dQw4w9WgXcQ"),
            "dQw4w9WgXcQ",
        )

    def test_leading_trailing_whitespace_stripped(self):
        self.assertEqual(extract_video_id("  dQw4w9WgXcQ  "), "dQw4w9WgXcQ")

    def test_invalid_input_raises_value_error(self):
        with self.assertRaises(ValueError):
            extract_video_id("not-a-youtube-url")

    def test_empty_string_raises_value_error(self):
        with self.assertRaises(ValueError):
            extract_video_id("")

    def test_too_short_id_raises_value_error(self):
        with self.assertRaises(ValueError):
            extract_video_id("short")

    def test_too_long_bare_id_raises_value_error(self):
        # 12 characters — one too many
        with self.assertRaises(ValueError):
            extract_video_id("dQw4w9WgXcQX")


# ---------------------------------------------------------------------------
# download_audio
# ---------------------------------------------------------------------------


class TestDownloadAudio(unittest.TestCase):
    """Tests for download_audio()."""

    @patch("splitter.subprocess.run")
    @patch("splitter.os.makedirs")
    def test_returns_expected_mp3_path(self, mock_makedirs, mock_run):
        mock_run.return_value = MagicMock(returncode=0)
        result = download_audio("dQw4w9WgXcQ", "/tmp/out")
        self.assertEqual(result, "/tmp/out/dQw4w9WgXcQ.mp3")

    @patch("splitter.subprocess.run")
    @patch("splitter.os.makedirs")
    def test_output_dir_is_created(self, mock_makedirs, mock_run):
        mock_run.return_value = MagicMock(returncode=0)
        download_audio("dQw4w9WgXcQ", "/tmp/out")
        mock_makedirs.assert_called_once_with("/tmp/out", exist_ok=True)

    @patch("splitter.subprocess.run")
    @patch("splitter.os.makedirs")
    def test_yt_dlp_called_with_correct_args(self, mock_makedirs, mock_run):
        mock_run.return_value = MagicMock(returncode=0)
        download_audio("dQw4w9WgXcQ", "/tmp/out")
        args, kwargs = mock_run.call_args
        cmd = args[0]
        self.assertEqual(cmd[0], "yt-dlp")
        self.assertIn("https://www.youtube.com/watch?v=dQw4w9WgXcQ", cmd)
        self.assertIn("mp3", cmd)
        self.assertTrue(kwargs.get("check"))

    @patch("splitter.subprocess.run")
    @patch("splitter.os.makedirs")
    def test_default_output_dir_is_current_directory(self, mock_makedirs, mock_run):
        mock_run.return_value = MagicMock(returncode=0)
        result = download_audio("dQw4w9WgXcQ")
        self.assertEqual(result, os.path.join(".", "dQw4w9WgXcQ.mp3"))


# ---------------------------------------------------------------------------
# split_karaoke
# ---------------------------------------------------------------------------


def _make_mock_audio_segment():
    """Return a minimal mock of an AudioSegment."""
    mono_mock = MagicMock()
    mono_mock.invert_phase.return_value = mono_mock
    mono_mock.overlay.return_value = mono_mock
    mono_mock.export.return_value = None

    audio_mock = MagicMock()
    audio_mock.channels = 2
    audio_mock.split_to_mono.return_value = (mono_mock, mono_mock)

    return audio_mock, mono_mock


class TestSplitKaraoke(unittest.TestCase):
    """Tests for split_karaoke()."""

    @patch("splitter.os.makedirs")
    @patch("splitter.os.path.isfile", return_value=True)
    @patch("splitter.AudioSegment")
    def test_returns_vocals_and_accompaniment_paths(
        self, mock_cls, mock_isfile, mock_makedirs
    ):
        audio_mock, mono_mock = _make_mock_audio_segment()
        mock_cls.from_mp3.return_value = audio_mock

        result = split_karaoke("/audio/dQw4w9WgXcQ.mp3", "/out")

        self.assertIn("vocals", result)
        self.assertIn("accompaniment", result)
        self.assertTrue(result["vocals"].endswith("dQw4w9WgXcQ_vocals.mp3"))
        self.assertTrue(
            result["accompaniment"].endswith("dQw4w9WgXcQ_accompaniment.mp3")
        )

    @patch("splitter.os.makedirs")
    @patch("splitter.os.path.isfile", return_value=True)
    @patch("splitter.AudioSegment")
    def test_export_called_twice(self, mock_cls, mock_isfile, mock_makedirs):
        audio_mock, mono_mock = _make_mock_audio_segment()
        mock_cls.from_mp3.return_value = audio_mock

        split_karaoke("/audio/dQw4w9WgXcQ.mp3", "/out")

        self.assertEqual(mono_mock.export.call_count, 2)
        export_formats = [c.kwargs.get("format") for c in mono_mock.export.call_args_list]
        self.assertEqual(export_formats, ["mp3", "mp3"])

    @patch("splitter.os.makedirs")
    @patch("splitter.os.path.isfile", return_value=True)
    @patch("splitter.AudioSegment")
    def test_mono_source_converted_to_stereo(
        self, mock_cls, mock_isfile, mock_makedirs
    ):
        audio_mock, mono_mock = _make_mock_audio_segment()
        audio_mock.channels = 1  # simulate mono source
        stereo_mock = MagicMock()
        stereo_mock.channels = 2
        stereo_mock.split_to_mono.return_value = (mono_mock, mono_mock)
        audio_mock.set_channels.return_value = stereo_mock
        mock_cls.from_mp3.return_value = audio_mock

        split_karaoke("/audio/dQw4w9WgXcQ.mp3", "/out")

        audio_mock.set_channels.assert_called_once_with(2)

    @patch("splitter.os.makedirs")
    @patch("splitter.os.path.isfile", return_value=False)
    def test_missing_file_raises_file_not_found(self, mock_isfile, mock_makedirs):
        with self.assertRaises(FileNotFoundError):
            split_karaoke("/nonexistent/file.mp3", "/out")

    @patch("splitter.os.makedirs")
    @patch("splitter.os.path.isfile", return_value=True)
    @patch("splitter.AudioSegment")
    def test_output_dir_created(self, mock_cls, mock_isfile, mock_makedirs):
        audio_mock, mono_mock = _make_mock_audio_segment()
        mock_cls.from_mp3.return_value = audio_mock

        split_karaoke("/audio/dQw4w9WgXcQ.mp3", "/custom/out")

        mock_makedirs.assert_called_with("/custom/out", exist_ok=True)


# ---------------------------------------------------------------------------
# process_video
# ---------------------------------------------------------------------------


class TestProcessVideo(unittest.TestCase):
    """Tests for process_video()."""

    @patch("splitter.split_karaoke")
    @patch("splitter.download_audio")
    def test_returns_all_expected_keys(self, mock_dl, mock_split):
        mock_dl.return_value = "/out/dQw4w9WgXcQ.mp3"
        mock_split.return_value = {
            "vocals": "/out/dQw4w9WgXcQ_vocals.mp3",
            "accompaniment": "/out/dQw4w9WgXcQ_accompaniment.mp3",
        }

        result = process_video("dQw4w9WgXcQ", "/out")

        self.assertEqual(result["video_id"], "dQw4w9WgXcQ")
        self.assertEqual(result["source_mp3"], "/out/dQw4w9WgXcQ.mp3")
        self.assertIn("vocals", result)
        self.assertIn("accompaniment", result)

    @patch("splitter.split_karaoke")
    @patch("splitter.download_audio")
    def test_accepts_full_url(self, mock_dl, mock_split):
        mock_dl.return_value = "/out/dQw4w9WgXcQ.mp3"
        mock_split.return_value = {
            "vocals": "/out/dQw4w9WgXcQ_vocals.mp3",
            "accompaniment": "/out/dQw4w9WgXcQ_accompaniment.mp3",
        }

        result = process_video(
            "https://www.youtube.com/watch?v=dQw4w9WgXcQ", "/out"
        )

        self.assertEqual(result["video_id"], "dQw4w9WgXcQ")
        mock_dl.assert_called_once_with("dQw4w9WgXcQ", "/out")

    @patch("splitter.split_karaoke")
    @patch("splitter.download_audio")
    def test_download_called_with_video_id_and_output_dir(
        self, mock_dl, mock_split
    ):
        mock_dl.return_value = "/out/abc123defgh.mp3"
        mock_split.return_value = {
            "vocals": "/out/abc123defgh_vocals.mp3",
            "accompaniment": "/out/abc123defgh_accompaniment.mp3",
        }

        process_video("abc123defgh", "/out")

        mock_dl.assert_called_once_with("abc123defgh", "/out")

    @patch("splitter.split_karaoke")
    @patch("splitter.download_audio")
    def test_split_called_with_downloaded_path_and_output_dir(
        self, mock_dl, mock_split
    ):
        mock_dl.return_value = "/out/abc123defgh.mp3"
        mock_split.return_value = {
            "vocals": "/out/abc123defgh_vocals.mp3",
            "accompaniment": "/out/abc123defgh_accompaniment.mp3",
        }

        process_video("abc123defgh", "/out")

        mock_split.assert_called_once_with("/out/abc123defgh.mp3", "/out")


if __name__ == "__main__":
    unittest.main()

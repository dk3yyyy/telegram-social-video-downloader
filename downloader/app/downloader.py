from __future__ import annotations

import json
import math
import os
import signal
import subprocess  # nosec B404
import tempfile
from pathlib import Path

from .config import Settings
from .store import JobRecord
from .telegram import TelegramClient

# Subprocess is required for fixed-path yt-dlp/ffmpeg tools; calls use argv lists.
_FORMAT_SELECTOR = "best[ext=mp4][vcodec^=avc1]/best[ext=mp4]/best"
_YTDLP = "/usr/local/bin/yt-dlp"
_FFPROBE = "/usr/bin/ffprobe"
_FFMPEG = "/usr/bin/ffmpeg"


class MediaProcessor:
    def __init__(self, settings: Settings, telegram: TelegramClient):
        self.settings = settings
        self.telegram = telegram

    def process(self, job: JobRecord) -> None:
        with tempfile.TemporaryDirectory(prefix="social-video-") as temp_dir:
            workdir = Path(temp_dir)
            media = self._download(job.url, workdir)
            probe = self._probe(media)
            if (
                probe["codec"] != "h264"
                or media.stat().st_size > self.settings.telegram_limit_bytes
            ):
                media = self._transcode(
                    media, workdir / "telegram-ready.mp4", probe["duration"]
                )
                probe = self._probe(media)
            if media.stat().st_size > self.settings.telegram_limit_bytes:
                raise RuntimeError(
                    "Video remains above Telegram's configured upload limit"
                )

            if media.stat().st_size <= self.settings.document_threshold_bytes:
                self.telegram.send_document(chat_id=job.chat_id, path=media)
            else:
                self.telegram.send_video(
                    chat_id=job.chat_id,
                    path=media,
                    width=probe["width"],
                    height=probe["height"],
                    duration=math.ceil(probe["duration"]),
                )

    def _download(self, url: str, workdir: Path) -> Path:
        template = str(workdir / "%(title).120s-%(id)s.%(ext)s")
        # No shell; URL host is allowlisted and placed after the option terminator.
        result = _run_command(
            [
                _YTDLP,
                "--no-playlist",
                "--restrict-filenames",
                "--merge-output-format",
                "mp4",
                "--format",
                _FORMAT_SELECTOR,
                "--max-filesize",
                str(self.settings.max_download_bytes),
                "--match-filters",
                f"duration <= {self.settings.max_duration_seconds}",
                "--output",
                template,
                "--",
                url,
            ],
            timeout=self.settings.job_timeout_seconds,
        )
        if result.returncode != 0:
            raise RuntimeError(f"yt-dlp failed with exit code {result.returncode}")
        candidates = [
            path
            for path in workdir.iterdir()
            if path.is_file()
            and path.suffix.lower() in {".mp4", ".mkv", ".webm", ".mov"}
        ]
        if not candidates:
            raise RuntimeError("yt-dlp produced no supported media file")
        media = max(candidates, key=lambda path: path.stat().st_size)
        if media.stat().st_size > self.settings.max_download_bytes:
            raise RuntimeError("Downloaded media exceeds the configured size limit")
        return media

    def _probe(self, path: Path) -> dict[str, float | int | str]:
        # Fixed binary and an application-generated temporary path.
        result = _run_command(
            [
                _FFPROBE,
                "-v",
                "error",
                "-select_streams",
                "v:0",
                "-show_entries",
                "stream=codec_name,width,height:format=duration",
                "-of",
                "json",
                str(path),
            ],
            timeout=30,
            capture_output=True,
            text=True,
        )
        if result.returncode != 0:
            raise RuntimeError("ffprobe could not inspect downloaded media")
        try:
            payload = json.loads(result.stdout)
            stream = payload["streams"][0]
            duration = float(payload["format"]["duration"])
            width = int(stream["width"])
            height = int(stream["height"])
            codec = str(stream["codec_name"])
        except (
            KeyError,
            IndexError,
            TypeError,
            ValueError,
            json.JSONDecodeError,
        ) as exc:
            raise RuntimeError(
                "Downloaded file does not contain a usable video stream"
            ) from exc
        if duration <= 0 or width <= 0 or height <= 0:
            raise RuntimeError("Downloaded video metadata is invalid")
        return {"duration": duration, "width": width, "height": height, "codec": codec}

    def _transcode(self, source: Path, destination: Path, duration: float) -> Path:
        if duration <= 0:
            raise RuntimeError("Cannot calculate a safe transcode bitrate")
        target_bits = self.settings.telegram_limit_bytes * 8 * 0.92
        audio_bitrate = 96_000
        video_bitrate = int(
            max(300_000, min(3_000_000, target_bits / duration - audio_bitrate))
        )
        # Fixed binary and application-generated temporary paths.
        result = _run_command(
            [
                _FFMPEG,
                "-y",
                "-i",
                str(source),
                "-map_metadata",
                "-1",
                "-c:v",
                "libx264",
                "-preset",
                "veryfast",
                "-pix_fmt",
                "yuv420p",
                "-b:v",
                str(video_bitrate),
                "-maxrate",
                str(video_bitrate),
                "-bufsize",
                str(video_bitrate * 2),
                "-c:a",
                "aac",
                "-b:a",
                "96k",
                "-movflags",
                "+faststart",
                str(destination),
            ],
            timeout=self.settings.job_timeout_seconds,
        )
        if result.returncode != 0 or not destination.exists():
            raise RuntimeError("ffmpeg could not create a Telegram-compatible video")
        return destination


def _run_command(
    args: list[str],
    *,
    timeout: float,
    capture_output: bool = False,
    text: bool = False,
) -> subprocess.CompletedProcess:
    """Run a fixed-path media tool and terminate its whole process group on timeout."""
    stream = subprocess.PIPE if capture_output else subprocess.DEVNULL
    process = subprocess.Popen(  # nosec B603
        args,
        stdout=stream,
        stderr=stream,
        text=text,
        start_new_session=True,
    )
    try:
        stdout, stderr = process.communicate(timeout=timeout)
    except subprocess.TimeoutExpired:
        _terminate_process_group(process)
        raise RuntimeError("Media tool timed out") from None
    return subprocess.CompletedProcess(args, process.returncode, stdout, stderr)


def _terminate_process_group(process: subprocess.Popen) -> None:
    for signal_number, wait_seconds in ((signal.SIGTERM, 2), (signal.SIGKILL, 2)):
        try:
            os.killpg(process.pid, signal_number)
        except ProcessLookupError:
            return
        except PermissionError:
            process.kill()
        try:
            process.wait(timeout=wait_seconds)
            return
        except subprocess.TimeoutExpired:
            continue

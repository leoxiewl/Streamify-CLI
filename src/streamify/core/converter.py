"""Local video-to-MP3 conversion backend using ffmpeg."""

from __future__ import annotations

import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path

VIDEO_EXTENSIONS = {".mp4", ".mov", ".mkv", ".avi", ".webm", ".m4v", ".flv", ".wmv", ".ts", ".m2ts"}


@dataclass
class ConversionResult:
    success: bool
    output_path: str | None = None
    error: str | None = None


class ConversionBackend:
    def check_ffmpeg(self) -> bool:
        return shutil.which("ffmpeg") is not None

    def find_video_files(self, directory: Path) -> list[Path]:
        files = []
        for ext in VIDEO_EXTENSIONS:
            files.extend(directory.glob(f"*{ext}"))
            files.extend(directory.glob(f"*{ext.upper()}"))
        return sorted(set(files))

    def convert_to_mp3(self, input_file: Path, output_file: Path, quality: str = "2") -> ConversionResult:
        output_file.parent.mkdir(parents=True, exist_ok=True)
        try:
            result = subprocess.run(
                [
                    "ffmpeg",
                    "-i", str(input_file),
                    "-vn",
                    "-acodec", "libmp3lame",
                    "-q:a", quality,
                    str(output_file),
                    "-y",
                ],
                capture_output=True,
                text=True,
            )
            if result.returncode != 0:
                # ffmpeg writes errors to stderr
                err = result.stderr.strip().splitlines()
                return ConversionResult(success=False, error=err[-1] if err else "ffmpeg failed")
            return ConversionResult(success=True, output_path=str(output_file))
        except FileNotFoundError:
            return ConversionResult(success=False, error="ffmpeg not found. Install: brew install ffmpeg")
        except Exception as e:
            return ConversionResult(success=False, error=str(e))

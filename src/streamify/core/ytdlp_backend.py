"""yt-dlp download backend."""

from __future__ import annotations

import shutil
from pathlib import Path
from typing import Any

import yt_dlp
from yt_dlp.networking.impersonate import ImpersonateTarget

from streamify.auth.session import get_bilibili_cookie_path, has_valid_bilibili_cookies
from streamify.core.downloader import DownloadResult, VideoInfo
from streamify.core.url_router import BILIBILI_PATTERNS
from streamify.progress import console, create_progress, make_progress_hook

QUALITY_MAP = {
    "best": "bestvideo+bestaudio/best",
    "1080": "bestvideo[height<=1080]+bestaudio/best[height<=1080]",
    "720": "bestvideo[height<=720]+bestaudio/best[height<=720]",
    "480": "bestvideo[height<=480]+bestaudio/best[height<=480]",
}


def _check_ffmpeg() -> None:
    if not shutil.which("ffmpeg"):
        console.print(
            "[yellow]⚠ ffmpeg not found. Video/audio merging may fail. "
            "Install: brew install ffmpeg[/yellow]"
        )


def _is_bilibili_url(url: str) -> bool:
    return any(pat.search(url) for pat in BILIBILI_PATTERNS)


def _build_opts(
    output_dir: Path,
    quality: str,
    audio_only: bool,
    cookies_from_browser: str | None,
    cookies_file: str | None,
    subtitle: bool,
    proxy: str | None,
    extra_opts: dict[str, Any],
    platform: str | None = None,
) -> dict[str, Any]:
    output_dir.mkdir(parents=True, exist_ok=True)

    fmt = QUALITY_MAP.get(quality, quality)
    if audio_only:
        fmt = "bestaudio/best"

    opts: dict[str, Any] = {
        "format": fmt,
        "outtmpl": str(output_dir / "%(title)s.%(ext)s"),
        "quiet": True,
        "no_warnings": True,
        "noprogress": True,
        "impersonate": ImpersonateTarget.from_str("chrome"),
    }

    # Always convert audio to MP3
    opts["postprocessors"] = [
        {
            "key": "FFmpegExtractAudio",
            "preferredcodec": "mp3",
            "preferredquality": "192",
        }
    ]

    # Store audio_only flag in opts for later detection
    opts["_audio_only"] = audio_only

    if cookies_from_browser:
        opts["cookiesfrombrowser"] = (cookies_from_browser,)
    elif cookies_file:
        opts["cookiefile"] = cookies_file
    elif platform == "bilibili" and has_valid_bilibili_cookies():
        # Auto-inject stored Bilibili cookies
        opts["cookiefile"] = str(get_bilibili_cookie_path())

    if subtitle:
        opts["writesubtitles"] = True
        opts["subtitleslangs"] = ["all"]
    if proxy:
        opts["proxy"] = proxy

    # Merge platform-specific options (extra_opts override)
    for k, v in extra_opts.items():
        if k == "http_headers" and k in opts:
            opts[k].update(v)
        else:
            opts[k] = v

    return opts


class YtdlpBackend:
    def download(self, url: str, opts: dict[str, Any]) -> DownloadResult:
        _check_ffmpeg()

        audio_only = opts.get("_audio_only", False)

        progress = create_progress()
        hook = make_progress_hook(progress)
        opts["progress_hooks"] = [hook]

        # First attempt
        result = self._try_download(url, opts, progress, audio_only)

        # If auth error on Bilibili, trigger QR login
        if not result.success and _is_auth_error(result.error or "") and _is_bilibili_url(url):
            console.print("[yellow]⚠ Bilibili authentication required.[/yellow]")
            cookie_path = self._auto_bilibili_login()
            if cookie_path:
                console.print("[green]✓ Login successful, retrying download...[/green]")
                retry_opts = {**opts, "cookiefile": cookie_path}
                retry_opts.pop("cookiesfrombrowser", None)
                retry_progress = create_progress()
                retry_hook = make_progress_hook(retry_progress)
                retry_opts["progress_hooks"] = [retry_hook]
                result = self._try_download(url, retry_opts, retry_progress, audio_only)

        return result

    def _auto_bilibili_login(self) -> str | None:
        """Trigger QR login and return cookie file path on success."""
        from streamify.auth.bilibili import bilibili_qr_login
        return bilibili_qr_login(console)

    def _try_download(self, url: str, opts: dict[str, Any], progress, audio_only: bool) -> DownloadResult:
        try:
            # Extract info first to get title
            with yt_dlp.YoutubeDL({**opts, "quiet": True, "noprogress": True}) as ydl:
                info = ydl.extract_info(url, download=False)
                if info is None:
                    return DownloadResult(success=False, error="Failed to extract video info")
                title = info.get("title", "Unknown")

            output_dir = Path(opts["outtmpl"]).parent

            if audio_only:
                # Audio-only mode: download audio and convert to MP3
                audio_opts = {**opts, "format": "bestaudio/best"}
                with progress:
                    with yt_dlp.YoutubeDL(audio_opts) as ydl:
                        ydl.extract_info(url, download=True)
                # Find the MP3 file
                mp3_files = list(output_dir.glob(f"{title}.*.mp3"))
                if mp3_files:
                    return DownloadResult(success=True, file_paths=[str(f) for f in mp3_files], title=title)
                # Try fallback
                m4a_files = list(output_dir.glob(f"{title}.*.m4a"))
                for m4a in m4a_files:
                    mp3_path = m4a.with_suffix(".mp3")
                    if mp3_path.exists():
                        return DownloadResult(success=True, file_paths=[str(mp3_path)], title=title)
                return DownloadResult(success=True, file_paths=[str(m4a_files[0])] if m4a_files else [], title=title)
            else:
                # Video mode: download video and audio separately
                video_files = []
                audio_files = []

                # Download video only (no postprocessors)
                video_opts = {**opts, "format": "bestvideo/best"}
                video_opts.pop("postprocessors", None)
                with progress:
                    with yt_dlp.YoutubeDL(video_opts) as ydl:
                        ydl.extract_info(url, download=True)
                # Find video file
                for ext in ["mp4", "mkv", "webm", "avi"]:
                    found = list(output_dir.glob(f"{title}.*.{ext}"))
                    if found:
                        video_files.extend([str(f) for f in found])
                        break

                # Download audio with conversion to MP3
                audio_opts = {**opts, "format": "bestaudio/best"}
                with progress:
                    with yt_dlp.YoutubeDL(audio_opts) as ydl:
                        ydl.extract_info(url, download=True)
                # Find MP3 file
                mp3_files = list(output_dir.glob(f"{title}.*.mp3"))
                if mp3_files:
                    audio_files = [str(f) for f in mp3_files]
                else:
                    # Fallback to m4a
                    m4a_files = list(output_dir.glob(f"{title}.*.m4a"))
                    audio_files = [str(f) for f in m4a_files]

                all_files = video_files + audio_files
                return DownloadResult(success=True, file_paths=all_files, title=title)

        except yt_dlp.utils.DownloadError as e:
            error_msg = str(e)
            hint = _get_error_hint(error_msg, url)
            return DownloadResult(success=False, error=f"{error_msg}\n{hint}" if hint else error_msg)
        except Exception as e:
            return DownloadResult(success=False, error=str(e))

        except yt_dlp.utils.DownloadError as e:
            error_msg = str(e)
            hint = _get_error_hint(error_msg, url)
            return DownloadResult(success=False, error=f"{error_msg}\n{hint}" if hint else error_msg)
        except Exception as e:
            return DownloadResult(success=False, error=str(e))

    def list_formats(self, url: str, opts: dict[str, Any]) -> list[dict[str, Any]]:
        opts_copy = {**opts, "listformats": False, "quiet": True}
        with yt_dlp.YoutubeDL(opts_copy) as ydl:
            info = ydl.extract_info(url, download=False)
            if info is None:
                return []
            return info.get("formats", [])

    def extract_info(self, url: str, opts: dict[str, Any]) -> VideoInfo:
        opts_copy = {**opts, "quiet": True}
        with yt_dlp.YoutubeDL(opts_copy) as ydl:
            info = ydl.extract_info(url, download=False)
            if info is None:
                raise ValueError("Failed to extract video info")
            return VideoInfo(
                title=info.get("title", "Unknown"),
                platform=info.get("extractor", "unknown"),
                url=url,
                duration=info.get("duration"),
                formats=info.get("formats", []),
            )


def build_download_opts(
    output_dir: Path,
    quality: str = "best",
    audio_only: bool = False,
    cookies_from_browser: str | None = None,
    cookies_file: str | None = None,
    subtitle: bool = False,
    proxy: str | None = None,
    extra_opts: dict[str, Any] | None = None,
    platform: str | None = None,
) -> dict[str, Any]:
    return _build_opts(
        output_dir=output_dir,
        quality=quality,
        audio_only=audio_only,
        cookies_from_browser=cookies_from_browser,
        cookies_file=cookies_file,
        subtitle=subtitle,
        proxy=proxy,
        extra_opts=extra_opts or {},
        platform=platform,
    )


def _is_auth_error(error_msg: str) -> bool:
    lower = error_msg.lower()
    return any(kw in lower for kw in [
        "sign in", "login", "cookie", "bot", "412", "precondition failed", "需要登录",
    ])


def _get_error_hint(error_msg: str, url: str) -> str | None:
    lower = error_msg.lower()
    if "login" in lower or "cookie" in lower or "需要登录" in lower or "412" in lower or "bot" in lower:
        if _is_bilibili_url(url):
            return "💡 Hint: Run 'python3 -m streamify login' to authenticate with Bilibili"
        return "💡 Hint: Try --cookies-from-browser chrome to use your browser cookies"
    if "geo" in lower or "region" in lower or "地区" in lower:
        return "💡 Hint: Try --proxy socks5://your-proxy:port for region-locked content"
    if "not found" in lower or "404" in lower:
        return "💡 Hint: Check if the URL is correct and the video still exists"
    return None

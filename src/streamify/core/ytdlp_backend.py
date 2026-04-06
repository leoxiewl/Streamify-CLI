"""yt-dlp download backend."""

from __future__ import annotations

import shutil
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yt_dlp
from yt_dlp.networking.impersonate import ImpersonateTarget

from streamify.auth.session import get_bilibili_cookie_path, has_valid_bilibili_cookies
from streamify.core.downloader import DownloadResult, PlaylistDownloadResult, VideoInfo
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
        opts["cookiefile"] = str(get_bilibili_cookie_path())

    if subtitle:
        opts["writesubtitles"] = True
        opts["subtitleslangs"] = ["zh-Hans", "zh-CN", "zh", "en"]
        opts["subtitle_outtmpl"] = "字幕%(title)s.%(ext)s"
    if proxy:
        opts["proxy"] = proxy

    for k, v in extra_opts.items():
        if k == "http_headers" and k in opts:
            opts[k].update(v)
        else:
            opts[k] = v

    return opts


def _build_transcript_opts(
    cookies_from_browser: str | None,
    cookies_file: str | None,
    langs: list[str],
    proxy: str | None,
    platform: str | None,
) -> dict[str, Any]:
    opts: dict[str, Any] = {
        "skip_download": True,
        "writesubtitles": True,
        "subtitleslangs": langs,
        "quiet": True,
        "no_warnings": True,
        "noprogress": True,
        "impersonate": ImpersonateTarget.from_str("chrome"),
    }
    if cookies_from_browser:
        opts["cookiesfrombrowser"] = (cookies_from_browser,)
    elif cookies_file:
        opts["cookiefile"] = cookies_file
    elif platform == "bilibili" and has_valid_bilibili_cookies():
        opts["cookiefile"] = str(get_bilibili_cookie_path())
    if proxy:
        opts["proxy"] = proxy
    return opts


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


def _srt_to_timestamp(seconds: float, video_url: str) -> str:
    """Convert seconds to [HH:MM:SS](bv_id?t=N) format clickable timestamp."""
    h = int(seconds // 3600)
    m = int((seconds % 3600) // 60)
    s = int(seconds % 60)
    ts = f"{h:02d}:{m:02d}:{s:02d}"
    # Strip existing query params and use ?t=N (B站跳转格式)
    base_url = video_url.split("?")[0]
    url = f"{base_url}?t={int(seconds)}"
    return f"[{ts}]({url})"


def _srt_to_plain_text(srt: str, video_url: str) -> str:
    """Parse SRT, prepend clickable timestamp to each block, join with blank lines."""
    blocks = []
    lines = srt.strip().splitlines()
    i = 0
    while i < len(lines):
        line = lines[i].strip()
        if "-->" in line:
            start_str = line.split("-->")[0].strip().replace(",", ".")
            seconds = sum(
                float(x) * mult
                for x, mult in zip(start_str.split(":"), [3600, 60, 1])
            )
            ts_link = _srt_to_timestamp(seconds, video_url)
            i += 1
            text_lines = []
            while i < len(lines) and lines[i].strip():
                text_lines.append(lines[i].strip())
                i += 1
            if text_lines:
                blocks.append(f"{ts_link} {''.join(text_lines)}")
        else:
            i += 1
    return "\n\n".join(blocks)


@dataclass
class TranscriptResult:
    success: bool
    title: str | None = None
    text: str | None = None
    language: str | None = None
    audio_files: list[str] = field(default_factory=list)
    error: str | None = None


class YtdlpBackend:
    def download(self, url: str, opts: dict[str, Any]) -> DownloadResult:
        _check_ffmpeg()

        audio_only = opts.get("_audio_only", False)

        progress = create_progress()
        hook = make_progress_hook(progress)
        opts["progress_hooks"] = [hook]

        result = self._try_download(url, opts, progress, audio_only)

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
            with yt_dlp.YoutubeDL({**opts, "quiet": True, "noprogress": True}) as ydl:
                info = ydl.extract_info(url, download=False)
                if info is None:
                    return DownloadResult(success=False, error="Failed to extract video info")
                title = info.get("title", "Unknown")

            output_dir = Path(opts["outtmpl"]).parent

            if audio_only:
                audio_opts = {**opts, "format": "bestaudio/best"}
                with progress:
                    with yt_dlp.YoutubeDL(audio_opts) as ydl:
                        ydl.extract_info(url, download=True)
                mp3_files = list(output_dir.glob(f"{title}.*.mp3"))
                if mp3_files:
                    return DownloadResult(success=True, file_paths=[str(f) for f in mp3_files], title=title)
                m4a_files = list(output_dir.glob(f"{title}.*.m4a"))
                for m4a in m4a_files:
                    mp3_path = m4a.with_suffix(".mp3")
                    if mp3_path.exists():
                        return DownloadResult(success=True, file_paths=[str(mp3_path)], title=title)
                return DownloadResult(success=True, file_paths=[str(m4a_files[0])] if m4a_files else [], title=title)
            else:
                video_opts = {**opts}
                video_opts["postprocessors"] = []
                output_dir = Path(opts["outtmpl"]).parent
                video_opts["outtmpl"] = str(output_dir / "%(title)s.mp4")
                video_opts["format"] = (
                    "bestvideo[vcodec^=avc1]+bestaudio[acodec^=mp4a]/"
                    "bestvideo[vcodec^=avc1]+bestaudio/"
                    "best"
                )
                video_opts["merge_output_format"] = "mp4"
                with progress:
                    with yt_dlp.YoutubeDL(video_opts) as ydl:
                        ydl.extract_info(url, download=True)
                for ext in ["mp4", "mkv", "webm", "avi"]:
                    found = list(output_dir.glob(f"*.{ext}"))
                    if found:
                        latest = max(found, key=lambda f: f.stat().st_mtime)
                        return DownloadResult(success=True, file_paths=[str(latest)], title=title)
                return DownloadResult(success=False, error="No video file found after download")

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

    def extract_transcript(
        self,
        url: str,
        opts: dict[str, Any],
        output_dir: Path | None = None,
    ) -> TranscriptResult:
        try:
            with yt_dlp.YoutubeDL(opts) as ydl:
                info = ydl.extract_info(url, download=False)
                if info is None:
                    return TranscriptResult(success=False, error="Failed to extract video info")

            title = info.get("title", "Unknown")
            subtitles: dict = info.get("subtitles") or {}
            if not subtitles:
                subtitles = info.get("automatic_captions") or {}

            # Filter out danmaku (弹幕) — it's not real subtitles
            subtitles = {k: v for k, v in subtitles.items() if k != "danmaku"}

            if not subtitles:
                if output_dir is None:
                    output_dir = Path.home() / "Downloads"
                audio_result = self._download_audio_fallback(url, title, output_dir)
                return TranscriptResult(
                    success=False,
                    title=title,
                    error="No subtitles found for this video.",
                    audio_files=audio_result,
                )

            langs_requested = opts.get("subtitleslangs", ["zh-Hans", "zh-CN", "zh", "en"])
            chosen_lang = None
            chosen_data = None
            for lang in langs_requested:
                if lang in subtitles:
                    chosen_lang = lang
                    chosen_data = subtitles[lang][0].get("data", "")
                    break

            if chosen_lang is None:
                chosen_lang = list(subtitles.keys())[0]
                chosen_data = subtitles[chosen_lang][0].get("data", "")

            if not chosen_data:
                return TranscriptResult(
                    success=False,
                    title=title,
                    error=f"Subtitles for '{chosen_lang}' are empty.",
                )

            plain_text = _srt_to_plain_text(chosen_data, url)
            return TranscriptResult(
                success=True,
                title=title,
                text=plain_text,
                language=chosen_lang,
            )

        except yt_dlp.utils.DownloadError as e:
            return TranscriptResult(success=False, error=str(e))
        except Exception as e:
            return TranscriptResult(success=False, error=str(e))

    def _download_audio_fallback(
        self, url: str, title: str, output_dir: Path
    ) -> list[str]:
        """Download audio only as fallback when no subtitles are available."""
        from streamify.progress import create_progress, make_progress_hook

        output_dir.mkdir(parents=True, exist_ok=True)
        audio_opts: dict[str, Any] = {
            "format": "bestaudio/best",
            "outtmpl": str(output_dir / "%(title)s.%(ext)s"),
            "quiet": True,
            "no_warnings": True,
            "noprogress": True,
            "impersonate": ImpersonateTarget.from_str("chrome"),
            "postprocessors": [
                {"key": "FFmpegExtractAudio", "preferredcodec": "mp3", "preferredquality": "192"}
            ],
        }
        if has_valid_bilibili_cookies():
            audio_opts["cookiefile"] = str(get_bilibili_cookie_path())

        try:
            with yt_dlp.YoutubeDL(audio_opts) as ydl:
                ydl.extract_info(url, download=True)
            mp3_files = list(output_dir.glob(f"{title}.*.mp3"))
            if mp3_files:
                return [str(f) for f in mp3_files]
            m4a_files = list(output_dir.glob(f"{title}.*.m4a"))
            return [str(f) for f in m4a_files]
        except Exception:
            return []

    def download_playlist(
        self,
        url: str,
        opts: dict[str, Any],
    ) -> PlaylistDownloadResult:
        """Download all videos in a playlist. Returns summary of all results."""
        _check_ffmpeg()

        # Extract playlist info without downloading
        try:
            with yt_dlp.YoutubeDL({**opts, "quiet": True, "noprogress": True}) as ydl:
                info = ydl.extract_info(url, download=False)
                if info is None:
                    return PlaylistDownloadResult(
                        success=False,
                        total=0,
                        success_count=0,
                        failed_count=0,
                        failures=[("Unknown", "Failed to extract playlist info")],
                    )
        except Exception as e:
            return PlaylistDownloadResult(
                success=False,
                total=0,
                success_count=0,
                failed_count=0,
                failures=[("Unknown", str(e))],
            )

        # Check if this is actually a playlist
        entries = info.get("entries") or []
        if not entries:
            # Not a playlist — treat as single video download
            # Filter out playlist-extraction flags from opts
            download_opts = {k: v for k, v in opts.items() if k not in ("quiet", "noprogress")}
            result = self.download(url, download_opts)
            return PlaylistDownloadResult(
                success=result.success,
                total=1,
                success_count=1 if result.success else 0,
                failed_count=0 if result.success else 1,
                failures=[] if result.success else [(result.title or "Unknown", result.error or "Unknown error")],
            )

        playlist_title = info.get("title", "Playlist")
        console.print(f"[dim]Playlist:[/dim] {playlist_title} ({len(entries)} videos)")
        console.print()

        success_count = 0
        failed_count = 0
        failures: list[tuple[str, str]] = []

        for i, entry in enumerate(entries, 1):
            if entry is None:
                continue
            # Get the URL for this entry
            entry_url = entry.get("url") or entry.get("webpage_url")
            entry_title = entry.get("title") or f"Part {i}"
            if not entry_url:
                failures.append((entry_title, "No URL found"))
                failed_count += 1
                continue

            console.print(f"[dim][{i}/{len(entries)}][/dim] {entry_title}")

            # Download this entry using the existing download logic
            entry_progress = create_progress()
            entry_hook = make_progress_hook(entry_progress)
            entry_opts = {**opts, "progress_hooks": [entry_hook]}

            try:
                result = self._try_download(entry_url, entry_opts, entry_progress, opts.get("_audio_only", False))
                if result.success:
                    success_count += 1
                    console.print(f"  [green]✓[/green] {result.file_paths}")
                else:
                    failed_count += 1
                    failures.append((entry_title, result.error or "Unknown error"))
                    console.print(f"  [red]✗[/red] {result.error}")
            except Exception as e:
                failed_count += 1
                failures.append((entry_title, str(e)))
                console.print(f"  [red]✗[/red] {e}")
            finally:
                entry_progress.stop()

        console.print()
        console.print(f"[dim]Summary:[/dim] {success_count} succeeded, {failed_count} failed")

        return PlaylistDownloadResult(
            success=failed_count == 0,
            total=len(entries),
            success_count=success_count,
            failed_count=failed_count,
            failures=failures,
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


def build_transcript_opts(
    cookies_from_browser: str | None = None,
    cookies_file: str | None = None,
    langs: list[str] | None = None,
    proxy: str | None = None,
    platform: str | None = None,
) -> dict[str, Any]:
    return _build_transcript_opts(
        cookies_from_browser=cookies_from_browser,
        cookies_file=cookies_file,
        langs=langs or ["zh-Hans", "zh-CN", "zh", "en"],
        proxy=proxy,
        platform=platform,
    )

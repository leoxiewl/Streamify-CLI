# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Command Generation Rules

When generating shell commands for the user:

1. **Use `python3` not `python`** — this Mac does not have `python` in PATH, only `python3`.
2. **Keep commands on a single line** — never split subcommands and arguments across lines; the terminal treats the second line as a separate command.

## Development Commands

```bash
# Install in editable mode
pip3 install -e .

# Run all tests
python3 -m pytest

# Run a single test file
python3 -m pytest tests/test_cli.py

# Run a single test by name
python3 -m pytest tests/test_cli.py::test_transcript_success

# Run the CLI directly (without install)
python3 -m streamify download "URL"
```

## Architecture

The codebase follows a layered design:

```
cli.py                  ← Typer CLI commands (download, transcript, login, logout)
core/url_router.py      ← Detects platform from URL, sets output dir + extra yt-dlp opts
core/ytdlp_backend.py   ← All yt-dlp interactions: download, playlist, transcript, formats
core/downloader.py      ← Result dataclasses (DownloadResult, PlaylistDownloadResult, VideoInfo)
auth/bilibili.py        ← QR code login flow via Bilibili passport API
auth/session.py         ← Cookie file persistence (~/.config/streamify/ or similar)
progress.py             ← Rich progress bar helpers shared across backend calls
```

**Data flow for `download`:**
1. `cli.py` calls `route_url(url)` → gets `platform`, `default_output_dir`, `ytdlp_extra_opts`
2. `build_download_opts()` assembles the full yt-dlp options dict
3. `YtdlpBackend.download()` runs yt-dlp; on Bilibili auth errors, auto-triggers QR login and retries

**Transcript flow:**
- Calls `extract_info` with `skip_download=True` + subtitle flags
- Prefers explicit subtitles over `automatic_captions`; filters out `danmaku` (弹幕)
- Falls back to downloading audio (MP3) when no subtitles exist, then instructs user to use external transcription
- SRT → Markdown conversion adds clickable `[HH:MM:SS](url?t=N)` timestamps

**Platform routing (`url_router.py`):**
- Bilibili default output: `~/Documents/B站视频/`
- YouTube default output: `~/Documents/YouTube视频/`
- Bilibili routes inject `Referer` header and enable subtitles by default

**Video download strategy (`_try_download`):**
- Prefers `avc1` (H.264) + `mp4a` codec combination for broad compatibility
- Always outputs `.mp4`; audio-only outputs `.mp3` via FFmpegExtractAudio postprocessor
- The `_audio_only` key is smuggled through the opts dict to signal audio-only mode

**Cookie precedence (for Bilibili):**
`--cookies-from-browser` > `--cookies` file > stored session cookies from `streamify login`

## Key Dependencies

- `yt-dlp` — all downloading and subtitle extraction
- `curl_cffi` + `ImpersonateTarget.from_str("chrome")` — browser impersonation to bypass bot detection
- `typer[all]` + `rich` — CLI and terminal output
- `qrcode` — terminal QR code rendering for Bilibili login
- `ffmpeg` (system binary) — required for video/audio merging; tool warns if missing

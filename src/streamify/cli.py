"""Streamify CLI — download Bilibili and YouTube videos."""

from __future__ import annotations

from pathlib import Path
from typing import Annotated, Optional

import typer
from rich.console import Console
from rich.table import Table

from streamify.core.converter import VIDEO_EXTENSIONS, ConversionBackend
from streamify.core.url_router import route_url
from streamify.core.ytdlp_backend import (
    YtdlpBackend,
    TranscriptResult,
    build_download_opts,
    build_transcript_opts,
)

app = typer.Typer(
    name="streamify",
    help="Download Bilibili and YouTube videos from URL.",
    add_completion=False,
)
console = Console()


@app.command()
def download(
    url: Annotated[str, typer.Argument(help="Video URL (Bilibili or YouTube)")],
    output: Annotated[
        Optional[Path],
        typer.Option("-o", "--output", help="Output directory"),
    ] = None,
    quality: Annotated[
        str,
        typer.Option("-q", "--quality", help="Quality: best, 1080, 720, 480"),
    ] = "best",
    audio_only: Annotated[
        bool,
        typer.Option("--audio-only", help="Extract audio only (MP3)"),
    ] = False,
    cookies_from_browser: Annotated[
        Optional[str],
        typer.Option("--cookies-from-browser", help="Browser to read cookies from (e.g., chrome, firefox)"),
    ] = None,
    cookies_file: Annotated[
        Optional[Path],
        typer.Option("--cookies", help="Path to Netscape cookie file"),
    ] = None,
    subtitle: Annotated[
        bool,
        typer.Option("--subtitle/--no-subtitle", help="Download subtitles"),
    ] = False,
    proxy: Annotated[
        Optional[str],
        typer.Option("--proxy", help="Proxy URL (e.g., socks5://127.0.0.1:1080)"),
    ] = None,
    list_formats: Annotated[
        bool,
        typer.Option("--list-formats", "-F", help="List available formats and exit"),
    ] = False,
    playlist: Annotated[
        bool,
        typer.Option("--playlist", help="Download all videos in a playlist/series"),
    ] = False,
):
    """Download a video from the given URL."""
    route = route_url(url)

    if route.platform == "unknown":
        console.print("[yellow]⚠ Unrecognized URL platform. Will try anyway.[/yellow]")

    output_dir = output if output else route.default_output_dir
    console.print(f"[dim]Platform:[/dim] {route.platform}")
    console.print(f"[dim]Output:[/dim]   {output_dir}")

    opts = build_download_opts(
        output_dir=output_dir,
        quality=quality,
        audio_only=audio_only,
        cookies_from_browser=cookies_from_browser,
        cookies_file=str(cookies_file) if cookies_file else None,
        subtitle=subtitle or route.platform == "bilibili",
        proxy=proxy,
        extra_opts=route.ytdlp_extra_opts,
        platform=route.platform,
    )

    backend = YtdlpBackend()

    if list_formats:
        _show_formats(backend, url, opts)
        return

    if playlist:
        console.print(f"[dim]Quality:[/dim]  {quality}")
        console.print()
        result = backend.download_playlist(url, opts)
        if result.failed_count > 0:
            console.print()
            console.print("[yellow]Failed videos:[/yellow]")
            for title, err in result.failures:
                console.print(f"  • {title}: {err}")
        if not result.success:
            raise typer.Exit(code=1)
        return

    console.print(f"[dim]Quality:[/dim]  {quality}")
    console.print()

    result = backend.download(url, opts)

    if result.success:
        console.print()
        console.print(f"[green]✓ Downloaded:[/green] {result.title}")
        for fp in result.file_paths:
            console.print(f"[green]  File:[/green] {fp}")
    else:
        console.print(f"\n[red]✗ Download failed:[/red] {result.error}")
        raise typer.Exit(code=1)


@app.command()
def transcript(
    url: Annotated[str, typer.Argument(help="Bilibili video URL")],
    lang: Annotated[
        str,
        typer.Option("--lang", "-l", help="Comma-separated language list, first available is used"),
    ] = "zh-Hans,zh-CN,zh,en",
    output: Annotated[
        Optional[Path],
        typer.Option("-o", "--output", help="Output file path (default: 字幕<title>.md in video directory)"),
    ] = None,
    cookies_from_browser: Annotated[
        Optional[str],
        typer.Option("--cookies-from-browser", help="Browser to read cookies from"),
    ] = None,
    cookies_file: Annotated[
        Optional[Path],
        typer.Option("--cookies", help="Path to Netscape cookie file"),
    ] = None,
    proxy: Annotated[
        Optional[str],
        typer.Option("--proxy", help="Proxy URL"),
    ] = None,
):
    """Extract plain-text transcript from a Bilibili video."""
    route = route_url(url)

    if route.platform == "unknown":
        console.print("[yellow]⚠ Unrecognized URL platform. Will try anyway.[/yellow]")
    elif route.platform != "bilibili":
        console.print(
            f"[yellow]⚠ transcript command is optimized for Bilibili. Detected: {route.platform}[/yellow]"
        )

    langs = [l.strip() for l in lang.split(",")]

    opts = build_transcript_opts(
        cookies_from_browser=cookies_from_browser,
        cookies_file=str(cookies_file) if cookies_file else None,
        langs=langs,
        proxy=proxy,
        platform=route.platform,
    )

    # Inject Bilibili-specific headers from route
    for k, v in route.ytdlp_extra_opts.items():
        if k in ("referer", "http_headers"):
            if k in opts:
                opts[k].update(v)
            else:
                opts[k] = v

    # output_dir is for audio fallback — always use video's default directory
    output_dir = route.default_output_dir

    backend = YtdlpBackend()
    result = backend.extract_transcript(url, opts, output_dir=output_dir)

    if result.success:
        # Default filename: 字幕<title>.md in the video's output directory
        if output is None and result.title:
            safe_title = "".join(c for c in result.title if c not in '<>:"/\\|?*\n')
            output = output_dir / f"字幕{safe_title}.md"
        console.print(f"[dim]Title:[/dim] {result.title}")
        console.print(f"[dim]Language:[/dim] {result.language}")
        if output:
            output.parent.mkdir(parents=True, exist_ok=True)
            output.write_text(result.text)
            console.print(f"[green]✓ Transcript saved to:[/green] {output}")
        else:
            console.print(result.text)
    else:
        console.print(f"[yellow]⚠ {result.error}[/yellow]")
        if result.audio_files:
            console.print()
            console.print("[dim]Audio has been downloaded for external transcription:[/dim]")
            for fp in result.audio_files:
                console.print(f"  {fp}")
            console.print()
            console.print(
                "[dim]You can upload the audio to[/dim] 讯飞听见 / 通义听悟 / Whisper [dim]to get a transcript.[/dim]"
            )
        raise typer.Exit(code=1)


@app.command()
def convert(
    path: Annotated[Path, typer.Argument(help="Video file or directory containing video files")],
    output: Annotated[
        Optional[Path],
        typer.Option("-o", "--output", help="Output directory (default: same as input)"),
    ] = None,
    quality: Annotated[
        str,
        typer.Option("-q", "--quality", help="MP3 quality 0-9, lower is better (default: 2 ≈ 190kbps VBR)"),
    ] = "2",
):
    """Convert local video file(s) to MP3."""
    backend = ConversionBackend()

    if not backend.check_ffmpeg():
        console.print("[red]✗ ffmpeg not found. Install: brew install ffmpeg[/red]")
        raise typer.Exit(code=1)

    if not path.exists():
        console.print(f"[red]✗ Path not found: {path}[/red]")
        raise typer.Exit(code=1)

    if path.is_file():
        if path.suffix.lower() not in VIDEO_EXTENSIONS:
            console.print(f"[yellow]⚠ '{path.suffix}' is not a recognized video format.[/yellow]")
            console.print(f"[dim]Supported: {', '.join(sorted(VIDEO_EXTENSIONS))}[/dim]")
            raise typer.Exit(code=1)
        files = [path]
    else:
        files = backend.find_video_files(path)
        if not files:
            console.print(f"[yellow]⚠ No video files found in {path}[/yellow]")
            raise typer.Exit(code=1)
        console.print(f"[dim]Found {len(files)} video file(s) in {path}[/dim]")
        console.print()

    success_count = 0
    failed_count = 0

    for i, input_file in enumerate(files, 1):
        out_dir = output if output else input_file.parent
        output_file = out_dir / f"{input_file.stem}.mp3"

        prefix = f"[dim][{i}/{len(files)}][/dim] " if len(files) > 1 else ""
        console.print(f"{prefix}{input_file.name}")

        with console.status("  Converting..."):
            result = backend.convert_to_mp3(input_file, output_file, quality)

        if result.success:
            console.print(f"  [green]✓[/green] {result.output_path}")
            success_count += 1
        else:
            console.print(f"  [red]✗[/red] {result.error}")
            failed_count += 1

    if len(files) > 1:
        console.print()
        console.print(f"[dim]Summary:[/dim] {success_count} converted, {failed_count} failed")

    if failed_count > 0:
        raise typer.Exit(code=1)


@app.command()
def login():
    """Log in to Bilibili via QR code."""
    from streamify.auth.bilibili import bilibili_qr_login

    result = bilibili_qr_login(console)
    if result:
        console.print(f"[green]✓ Logged in! Cookies saved to {result}[/green]")
    else:
        console.print("[red]✗ Login failed or cancelled.[/red]")
        raise typer.Exit(code=1)


@app.command()
def logout():
    """Remove stored Bilibili login session."""
    from streamify.auth.session import delete_bilibili_cookies

    delete_bilibili_cookies()
    console.print("[green]✓ Logged out. Bilibili cookies cleared.[/green]")


def _show_formats(backend: YtdlpBackend, url: str, opts: dict) -> None:
    formats = backend.list_formats(url, opts)
    if not formats:
        console.print("[yellow]No formats found.[/yellow]")
        return

    table = Table(title="Available Formats")
    table.add_column("ID", style="cyan")
    table.add_column("Ext", style="green")
    table.add_column("Resolution")
    table.add_column("Size", justify="right")
    table.add_column("Note")

    for f in formats:
        fmt_id = f.get("format_id", "?")
        ext = f.get("ext", "?")
        res = f.get("resolution", "audio" if f.get("vcodec") == "none" else "?")
        size = f.get("filesize") or f.get("filesize_approx")
        size_str = f"{size / 1024 / 1024:.1f}MB" if size else "?"
        note = f.get("format_note", "")
        table.add_row(fmt_id, ext, res, size_str, note)

    console.print(table)


if __name__ == "__main__":
    app()

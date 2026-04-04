"""Rich progress bar driven by yt-dlp progress hooks."""

from __future__ import annotations

from rich.console import Console
from rich.progress import (
    BarColumn,
    DownloadColumn,
    Progress,
    TextColumn,
    TimeRemainingColumn,
    TransferSpeedColumn,
)

console = Console()


def create_progress() -> Progress:
    return Progress(
        TextColumn("[bold blue]{task.fields[filename]}", justify="right"),
        BarColumn(bar_width=40),
        "[progress.percentage]{task.percentage:>3.1f}%",
        DownloadColumn(),
        TransferSpeedColumn(),
        TimeRemainingColumn(),
        console=console,
    )


def make_progress_hook(progress: Progress) -> callable:
    """Return a yt-dlp progress_hook that drives a Rich progress bar."""
    task_map: dict[str, int] = {}

    def hook(d: dict) -> None:
        filename = d.get("filename", "unknown")
        short_name = filename.rsplit("/", 1)[-1]

        if d["status"] == "downloading":
            total = d.get("total_bytes") or d.get("total_bytes_estimate") or 0
            downloaded = d.get("downloaded_bytes", 0)

            if filename not in task_map:
                task_id = progress.add_task("download", filename=short_name, total=total)
                task_map[filename] = task_id
            else:
                task_id = task_map[filename]
                if total:
                    progress.update(task_id, total=total)

            progress.update(task_id, completed=downloaded)

        elif d["status"] == "finished":
            if filename in task_map:
                task_id = task_map[filename]
                progress.update(task_id, completed=progress.tasks[task_id].total or 0)

    return hook

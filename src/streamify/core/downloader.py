"""Downloader protocol — abstraction over download backends."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Protocol, runtime_checkable


@dataclass
class VideoInfo:
    title: str
    platform: str
    url: str
    duration: int | None = None
    formats: list[dict[str, Any]] = field(default_factory=list)


@dataclass
class DownloadResult:
    success: bool
    file_paths: list[str] = field(default_factory=list)
    title: str | None = None
    error: str | None = None


@runtime_checkable
class Downloader(Protocol):
    def download(self, url: str, opts: dict[str, Any]) -> DownloadResult: ...
    def list_formats(self, url: str, opts: dict[str, Any]) -> list[dict[str, Any]]: ...
    def extract_info(self, url: str, opts: dict[str, Any]) -> VideoInfo: ...


@dataclass
class PlaylistDownloadResult:
    success: bool
    total: int
    success_count: int
    failed_count: int
    failures: list[tuple[str, str]] = field(default_factory=list)  # [(title, error), ...]

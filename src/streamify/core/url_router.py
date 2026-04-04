"""Detect platform from URL and return platform-specific defaults."""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

BILIBILI_PATTERNS = [
    re.compile(r"https?://(?:www\.)?bilibili\.com/video/"),
    re.compile(r"https?://(?:www\.)?bilibili\.com/bangumi/"),
    re.compile(r"https?://(?:www\.)?b23\.tv/"),
    re.compile(r"https?://m\.bilibili\.com/video/"),
]

YOUTUBE_PATTERNS = [
    re.compile(r"https?://(?:www\.)?youtube\.com/watch"),
    re.compile(r"https?://(?:www\.)?youtube\.com/shorts/"),
    re.compile(r"https?://(?:www\.)?youtube\.com/playlist"),
    re.compile(r"https?://youtu\.be/"),
    re.compile(r"https?://(?:www\.)?youtube\.com/live/"),
]

DEFAULT_BASE = Path.home() / "Documents"


@dataclass
class RouteResult:
    platform: str  # "bilibili" | "youtube" | "unknown"
    default_output_dir: Path
    ytdlp_extra_opts: dict


def route_url(url: str) -> RouteResult:
    for pat in BILIBILI_PATTERNS:
        if pat.search(url):
            return RouteResult(
                platform="bilibili",
                default_output_dir=DEFAULT_BASE / "B站视频",
                ytdlp_extra_opts={
                    "referer": "https://www.bilibili.com",
                    "http_headers": {
                        "Referer": "https://www.bilibili.com",
                        "User-Agent": (
                            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                            "AppleWebKit/537.36 (KHTML, like Gecko) "
                            "Chrome/125.0.0.0 Safari/537.36"
                        ),
                    },
                    "writesubtitles": True,
                    "subtitleslangs": ["zh-Hans", "zh-CN", "zh", "en"],
                },
            )

    for pat in YOUTUBE_PATTERNS:
        if pat.search(url):
            return RouteResult(
                platform="youtube",
                default_output_dir=DEFAULT_BASE / "YouTube视频",
                ytdlp_extra_opts={},
            )

    return RouteResult(
        platform="unknown",
        default_output_dir=DEFAULT_BASE / "Videos",
        ytdlp_extra_opts={},
    )

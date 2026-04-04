"""Tests for URL routing."""

from pathlib import Path

from streamify.core.url_router import route_url


def test_bilibili_standard_url():
    r = route_url("https://www.bilibili.com/video/BV1GJ411x7h7")
    assert r.platform == "bilibili"
    assert "B站视频" in str(r.default_output_dir)
    assert r.ytdlp_extra_opts.get("referer") == "https://www.bilibili.com"


def test_bilibili_mobile_url():
    r = route_url("https://m.bilibili.com/video/BV1GJ411x7h7")
    assert r.platform == "bilibili"


def test_bilibili_short_url():
    r = route_url("https://b23.tv/abc123")
    assert r.platform == "bilibili"


def test_bilibili_bangumi():
    r = route_url("https://www.bilibili.com/bangumi/play/ep12345")
    assert r.platform == "bilibili"


def test_youtube_standard():
    r = route_url("https://www.youtube.com/watch?v=dQw4w9WgXcQ")
    assert r.platform == "youtube"
    assert "YouTube视频" in str(r.default_output_dir)


def test_youtube_short_url():
    r = route_url("https://youtu.be/dQw4w9WgXcQ")
    assert r.platform == "youtube"


def test_youtube_shorts():
    r = route_url("https://www.youtube.com/shorts/abc123")
    assert r.platform == "youtube"


def test_youtube_live():
    r = route_url("https://www.youtube.com/live/abc123")
    assert r.platform == "youtube"


def test_youtube_playlist():
    r = route_url("https://www.youtube.com/playlist?list=PLxyz")
    assert r.platform == "youtube"


def test_unknown_url():
    r = route_url("https://example.com/video/123")
    assert r.platform == "unknown"


def test_bilibili_subtitles_enabled():
    r = route_url("https://www.bilibili.com/video/BV1GJ411x7h7")
    assert r.ytdlp_extra_opts.get("writesubtitles") is True

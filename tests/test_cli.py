"""Tests for CLI argument parsing."""

from unittest.mock import MagicMock, patch

from typer.testing import CliRunner

from streamify.cli import app

runner = CliRunner()


def test_help():
    result = runner.invoke(app, ["--help"])
    assert result.exit_code == 0
    assert "download" in result.output.lower()


def test_download_help():
    result = runner.invoke(app, ["download", "--help"])
    assert result.exit_code == 0
    assert "Download a video" in result.output


def test_missing_url():
    result = runner.invoke(app, ["download"])
    assert result.exit_code != 0


@patch("streamify.cli.YtdlpBackend")
def test_bilibili_url_routes_correctly(mock_backend_cls):
    mock_backend = MagicMock()
    mock_backend.download.return_value = MagicMock(
        success=True, file_path="/tmp/test.mp4", title="Test Video"
    )
    mock_backend_cls.return_value = mock_backend

    result = runner.invoke(app, ["download", "https://www.bilibili.com/video/BV1test", "-q", "720"])
    assert "bilibili" in result.output.lower()
    mock_backend.download.assert_called_once()


@patch("streamify.cli.YtdlpBackend")
def test_youtube_url_routes_correctly(mock_backend_cls):
    mock_backend = MagicMock()
    mock_backend.download.return_value = MagicMock(
        success=True, file_path="/tmp/test.mp4", title="Test Video"
    )
    mock_backend_cls.return_value = mock_backend

    result = runner.invoke(app, ["download", "https://www.youtube.com/watch?v=test123", "-q", "1080"])
    assert "youtube" in result.output.lower()
    mock_backend.download.assert_called_once()


@patch("streamify.cli.YtdlpBackend")
def test_custom_output_dir(mock_backend_cls):
    mock_backend = MagicMock()
    mock_backend.download.return_value = MagicMock(
        success=True, file_path="/tmp/test.mp4", title="Test"
    )
    mock_backend_cls.return_value = mock_backend

    result = runner.invoke(app, ["download", "https://youtu.be/test", "-o", "/tmp/custom"])
    assert "/tmp/custom" in result.output


@patch("streamify.cli.YtdlpBackend")
def test_download_failure(mock_backend_cls):
    mock_backend = MagicMock()
    mock_backend.download.return_value = MagicMock(
        success=False, error="Network error"
    )
    mock_backend_cls.return_value = mock_backend

    result = runner.invoke(app, ["download", "https://youtu.be/test"])
    assert result.exit_code == 1
    assert "failed" in result.output.lower()


def test_login_command_exists():
    result = runner.invoke(app, ["login", "--help"])
    assert result.exit_code == 0
    assert "QR code" in result.output


def test_logout_command_exists():
    result = runner.invoke(app, ["logout", "--help"])
    assert result.exit_code == 0


def test_transcript_help():
    result = runner.invoke(app, ["transcript", "--help"])
    assert result.exit_code == 0
    assert "transcript" in result.output.lower()


@patch("streamify.cli.YtdlpBackend")
def test_transcript_success(mock_backend_cls, tmp_path):
    mock_backend = MagicMock()
    mock_backend.extract_transcript.return_value = MagicMock(
        success=True,
        title="Test Video",
        text="[00:00:01](url#t=1) 第一句\n\n[00:00:05](url#t=5) 第二句",
        language="zh-Hans",
        audio_files=[],
    )
    mock_backend_cls.return_value = mock_backend

    result = runner.invoke(
        app,
        ["transcript", "https://www.bilibili.com/video/BV1test", "-o", str(tmp_path / "transcript.md")],
    )
    assert result.exit_code == 0
    assert "Test Video" in result.output
    assert (tmp_path / "transcript.md").read_text() == "[00:00:01](url#t=1) 第一句\n\n[00:00:05](url#t=5) 第二句"


@patch("streamify.cli.YtdlpBackend")
def test_transcript_default_filename(mock_backend_cls, tmp_path):
    """Without -o, transcript is saved as 字幕<title>.md in default dir."""
    mock_backend = MagicMock()
    mock_backend.extract_transcript.return_value = MagicMock(
        success=True,
        title="Test Video",
        text="字幕内容",
        language="zh-Hans",
        audio_files=[],
    )
    mock_backend_cls.return_value = mock_backend

    # Patch the default output dir to use tmp_path
    with patch("streamify.core.url_router.DEFAULT_BASE", tmp_path):
        result = runner.invoke(
            app,
            ["transcript", "https://www.bilibili.com/video/BV1test"],
        )
    assert result.exit_code == 0
    assert "字幕Test Video.md" in result.output
    assert (tmp_path / "B站视频" / "字幕Test Video.md").read_text() == "字幕内容"


@patch("streamify.cli.YtdlpBackend")
def test_transcript_no_subtitles_fallback(mock_backend_cls):
    mock_backend = MagicMock()
    mock_backend.extract_transcript.return_value = MagicMock(
        success=False,
        title="Test Video",
        error="No subtitles found for this video.",
        audio_files=["/tmp/Test_Video.mp3"],
    )
    mock_backend_cls.return_value = mock_backend

    result = runner.invoke(
        app,
        ["transcript", "https://www.bilibili.com/video/BV1test"],
    )
    assert result.exit_code == 1
    assert "No subtitles" in result.output
    assert "Test_Video.mp3" in result.output
    assert "讯飞听见" in result.output or "Whisper" in result.output


@patch("streamify.cli.YtdlpBackend")
def test_transcript_language_option(mock_backend_cls):
    mock_backend = MagicMock()
    mock_backend.extract_transcript.return_value = MagicMock(
        success=True,
        title="Test",
        text="...",
        language="en",
        audio_files=[],
    )
    mock_backend_cls.return_value = mock_backend

    result = runner.invoke(
        app,
        ["transcript", "https://www.bilibili.com/video/BV1test", "-l", "en,zh-Hans"],
    )
    assert result.exit_code == 0


@patch("streamify.cli.YtdlpBackend")
def test_download_playlist_all_success(mock_backend_cls):
    from streamify.core.downloader import PlaylistDownloadResult

    mock_backend = MagicMock()
    mock_backend.download_playlist.return_value = PlaylistDownloadResult(
        success=True,
        total=3,
        success_count=3,
        failed_count=0,
        failures=[],
    )
    mock_backend_cls.return_value = mock_backend

    result = runner.invoke(
        app,
        ["download", "https://www.bilibili.com/video/BV17V4y147Nj/", "--playlist"],
    )
    assert result.exit_code == 0
    mock_backend.download_playlist.assert_called_once()


@patch("streamify.cli.YtdlpBackend")
def test_download_playlist_partial_failure(mock_backend_cls):
    from streamify.core.downloader import PlaylistDownloadResult

    mock_backend = MagicMock()
    mock_backend.download_playlist.return_value = PlaylistDownloadResult(
        success=False,
        total=3,
        success_count=2,
        failed_count=1,
        failures=[("Part 2", "Download failed")],
    )
    mock_backend_cls.return_value = mock_backend

    result = runner.invoke(
        app,
        ["download", "https://www.bilibili.com/video/BV17V4y147Nj/", "--playlist"],
    )
    assert result.exit_code == 1
    assert "Failed videos" in result.output
    assert "Part 2" in result.output


@patch("streamify.cli.YtdlpBackend")
def test_download_playlist_flag_hidden_for_normal(mock_backend_cls):
    """Without --playlist flag, download_playlist should not be called."""
    mock_backend = MagicMock()
    mock_backend.download.return_value = MagicMock(success=True, file_paths=["/tmp/test.mp4"], title="Test")
    mock_backend_cls.return_value = mock_backend

    result = runner.invoke(
        app,
        ["download", "https://www.bilibili.com/video/BV1test"],
    )
    assert result.exit_code == 0
    mock_backend.download_playlist.assert_not_called()
    mock_backend.download.assert_called_once()

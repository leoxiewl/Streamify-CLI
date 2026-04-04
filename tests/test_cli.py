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

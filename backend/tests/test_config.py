"""Tests for application configuration."""

from pathlib import Path
from unittest.mock import patch

from app.config import _read_version, settings


def test_app_version_matches_version_file():
    """config.app_version must match the VERSION file at the repo root."""
    version_file = Path(__file__).resolve().parent.parent.parent / "VERSION"
    expected = version_file.read_text().strip()
    assert settings.app_version == expected


def test_read_version_fallback_when_file_missing(tmp_path):
    """_read_version returns '0.0.0' when VERSION file does not exist."""
    fake_config = tmp_path / "app" / "config.py"
    fake_config.parent.mkdir(parents=True)
    fake_config.touch()
    # Patch __file__ resolution so the computed path points to tmp_path (no VERSION)
    with patch("app.config.Path") as mock_path_cls:
        # Make Path(__file__).resolve().parent.parent.parent / "VERSION" point to
        # a non-existent file inside tmp_path
        mock_resolve = mock_path_cls.return_value.resolve.return_value
        mock_resolve.parent.parent.parent.__truediv__ = lambda self, name: tmp_path / name
        result = _read_version()
    assert result == "0.0.0"


def test_read_version_reads_file_content(tmp_path):
    """_read_version reads and strips the VERSION file content."""
    version_file = tmp_path / "VERSION"
    version_file.write_text("  1.2.3\n")
    with patch("app.config.Path") as mock_path_cls:
        mock_resolve = mock_path_cls.return_value.resolve.return_value
        mock_resolve.parent.parent.parent.__truediv__ = lambda self, name: tmp_path / name
        result = _read_version()
    assert result == "1.2.3"

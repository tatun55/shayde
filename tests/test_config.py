"""Tests for configuration loading."""

import pytest
from pathlib import Path

from shayde.config.schema import ShaydeConfig, ViewportConfig
from shayde.config.loader import load_config, get_app_url_from_env, detect_vite_port


def test_default_config():
    """Test default configuration."""
    config = ShaydeConfig.get_default()

    assert config.version == 1
    assert config.proxy.port == 9999
    assert config.docker.playwright_version == "1.48.0"
    assert "desktop" in config.viewports
    assert config.viewports["desktop"].width == 1920


def test_viewport_config():
    """Test viewport configuration."""
    viewport = ViewportConfig(width=375, height=812, device_scale_factor=2)

    assert viewport.width == 375
    assert viewport.height == 812
    assert viewport.device_scale_factor == 2


def test_get_app_url_from_env(temp_project, monkeypatch):
    """Test reading APP_URL from .env file."""
    monkeypatch.chdir(temp_project)

    url = get_app_url_from_env()
    assert url == "http://example.test"


def test_get_app_url_missing_env(tmp_path, monkeypatch):
    """Test handling missing .env file."""
    monkeypatch.chdir(tmp_path)

    url = get_app_url_from_env()
    assert url is None


def test_config_merge():
    """Test configuration merging."""
    config = ShaydeConfig(
        app={"base_url": "http://custom.test"},
        proxy={"port": 8888},
    )

    assert config.app.base_url == "http://custom.test"
    assert config.proxy.port == 8888
    # Other values should be defaults
    assert config.docker.playwright_version == "1.48.0"

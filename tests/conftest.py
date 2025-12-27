"""Pytest configuration and fixtures."""

import pytest
from pathlib import Path


@pytest.fixture
def temp_project(tmp_path):
    """Create a temporary project directory with .env file."""
    env_file = tmp_path / ".env"
    env_file.write_text("APP_URL=http://example.test\n")
    return tmp_path


@pytest.fixture
def sample_config():
    """Return sample configuration dict."""
    return {
        "version": 1,
        "app": {
            "base_url": "http://example.test",
        },
        "proxy": {
            "enabled": True,
            "port": 9999,
            "vite_port": 5173,
        },
    }

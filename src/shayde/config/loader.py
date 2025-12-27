"""Configuration loader for Shayde."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Dict, Optional

import yaml

from shayde.config.schema import ShaydeConfig


CONFIG_FILENAMES = [".shayde.yaml", ".shayde.yml", "shayde.yaml", "shayde.yml"]
GLOBAL_CONFIG_DIR = Path.home() / ".config" / "shayde"
GLOBAL_CONFIG_FILE = GLOBAL_CONFIG_DIR / "config.yaml"


def find_config_file(start_dir: Optional[Path] = None) -> Optional[Path]:
    """Find configuration file in current or parent directories."""
    if start_dir is None:
        start_dir = Path.cwd()

    current = start_dir.resolve()

    # Search upward for config file
    while current != current.parent:
        for filename in CONFIG_FILENAMES:
            config_path = current / filename
            if config_path.exists():
                return config_path
        current = current.parent

    return None


def load_yaml_file(path: Path) -> Dict[str, Any]:
    """Load YAML configuration file."""
    if not path.exists():
        return {}

    with open(path, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f)
        return data if data else {}


def get_app_url_from_env(env_file: str = ".env", env_var: str = "APP_URL") -> Optional[str]:
    """Read APP_URL from .env file."""
    env_path = Path.cwd() / env_file
    if not env_path.exists():
        return None

    with open(env_path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line.startswith(f"{env_var}="):
                return line.split("=", 1)[1].strip().strip('"').strip("'")

    return None


def detect_vite_port() -> Optional[int]:
    """Detect Vite dev server port from hot file or config."""
    # Check Laravel's hot file
    hot_file = Path.cwd() / "public" / "hot"
    if hot_file.exists():
        content = hot_file.read_text().strip()
        # Parse URL like "http://0.0.0.0:5174" or "http://localhost:5173"
        import re
        match = re.search(r":(\d+)", content)
        if match:
            return int(match.group(1))

    # Default Vite port
    return 5173


def load_config(
    config_file: Optional[Path] = None,
    project_dir: Optional[Path] = None,
) -> ShaydeConfig:
    """Load and merge configuration from all sources.

    Priority (later overrides earlier):
    1. Built-in defaults
    2. Global config (~/.config/shayde/config.yaml)
    3. Project config (.shayde.yaml)
    4. Explicit config file (if provided)
    """
    # Start with defaults
    config_data: Dict[str, Any] = {}

    # Load global config
    if GLOBAL_CONFIG_FILE.exists():
        global_data = load_yaml_file(GLOBAL_CONFIG_FILE)
        config_data = _deep_merge(config_data, global_data)

    # Find and load project config
    if config_file is None:
        config_file = find_config_file(project_dir)

    if config_file and config_file.exists():
        project_data = load_yaml_file(config_file)
        config_data = _deep_merge(config_data, project_data)

    # Create config object
    config = ShaydeConfig(**config_data) if config_data else ShaydeConfig()

    # Auto-detect APP_URL if not set
    if config.app.base_url is None:
        detected_url = get_app_url_from_env(config.app.env_file, config.app.env_var)
        if detected_url:
            config.app.base_url = detected_url

    # Auto-detect Vite port if not set
    if config.proxy.vite_port is None:
        detected_port = detect_vite_port()
        if detected_port:
            config.proxy.vite_port = detected_port

    return config


def _deep_merge(base: Dict[str, Any], override: Dict[str, Any]) -> Dict[str, Any]:
    """Deep merge two dictionaries."""
    result = base.copy()

    for key, value in override.items():
        if key in result and isinstance(result[key], dict) and isinstance(value, dict):
            result[key] = _deep_merge(result[key], value)
        else:
            result[key] = value

    return result


def save_config(config: ShaydeConfig, path: Path) -> None:
    """Save configuration to YAML file."""
    path.parent.mkdir(parents=True, exist_ok=True)

    data = config.model_dump(exclude_defaults=True)

    with open(path, "w", encoding="utf-8") as f:
        yaml.dump(data, f, default_flow_style=False, allow_unicode=True, sort_keys=False)

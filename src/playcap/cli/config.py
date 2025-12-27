"""Config CLI commands."""

from __future__ import annotations

from pathlib import Path
from typing import Optional

import typer
from rich.console import Console
from rich.syntax import Syntax
from rich.table import Table
import yaml

from playcap.config.loader import load_config, CONFIG_FILENAMES
from playcap.config.schema import PlayCapConfig

console = Console()
app = typer.Typer(no_args_is_help=True)


@app.command("init")
def config_init(
    output: Optional[Path] = typer.Option(
        None, "--output", "-o", help="Output file path"
    ),
    force: bool = typer.Option(
        False, "--force", "-f", help="Overwrite existing config"
    ),
):
    """Create a new .playcap.yaml configuration file."""
    # Default output path
    if output is None:
        output = Path.cwd() / ".playcap.yaml"

    # Check if file exists
    if output.exists() and not force:
        console.print(f"[yellow]Warning:[/yellow] {output} already exists. Use --force to overwrite.")
        raise typer.Exit(1)

    # Generate default config
    config = PlayCapConfig.get_default()

    # Convert to YAML with comments
    yaml_content = _generate_config_yaml(config)

    # Write file
    output.write_text(yaml_content)
    console.print(f"[green]✓[/green] Created: {output}")


def _generate_config_yaml(config: PlayCapConfig) -> str:
    """Generate YAML config with helpful comments."""
    return f"""# PlayCap Configuration
# https://github.com/playcap/playcap

version: 1

# Application URL configuration
app:
  # Base URL (auto-detected from .env APP_URL if not specified)
  base_url: null
  env_file: .env
  env_var: APP_URL

# Dev server proxy configuration
proxy:
  enabled: true
  port: {config.proxy.port}
  # Vite port (auto-detected from public/hot if not specified)
  vite_port: null
  websocket: true

# Docker container configuration
docker:
  playwright_version: "{config.docker.playwright_version}"
  container_name: "{config.docker.container_name}"
  ws_port: {config.docker.ws_port}
  auto_start: true
  auto_stop: false

# Screenshot output configuration
output:
  directory: "{config.output.directory}"
  filename_pattern: "{config.output.filename_pattern}"
  date_format: "{config.output.date_format}"
  time_format: "{config.output.time_format}"

# Viewport presets
viewports:
  mobile:
    width: 375
    height: 812
    device_scale_factor: 2
  tablet:
    width: 768
    height: 1024
    device_scale_factor: 1
  desktop:
    width: 1920
    height: 1080
    device_scale_factor: 1

# Default capture settings
capture:
  default_viewport: desktop
  wait_until: networkidle
  wait_after: 0
  full_page: false

# Visual regression settings
regression:
  baseline_dir: "{config.regression.baseline_dir}"
  diff_dir: "{config.regression.diff_dir}"
  threshold: {config.regression.threshold}
"""


@app.command("show")
def config_show(
    format: str = typer.Option(
        "yaml", "--format", "-f", help="Output format (yaml, table)"
    ),
):
    """Display current configuration."""
    config = load_config()

    if format == "yaml":
        data = config.model_dump()
        yaml_str = yaml.dump(data, default_flow_style=False, allow_unicode=True)
        syntax = Syntax(yaml_str, "yaml", theme="monokai")
        console.print(syntax)

    elif format == "table":
        table = Table(title="PlayCap Configuration")
        table.add_column("Setting", style="cyan")
        table.add_column("Value", style="green")

        table.add_row("App URL", config.app.base_url or "(auto-detect)")
        table.add_row("Proxy Port", str(config.proxy.port))
        table.add_row("Vite Port", str(config.proxy.vite_port or "(auto-detect)"))
        table.add_row("Docker Container", config.docker.container_name)
        table.add_row("Playwright Version", config.docker.playwright_version)
        table.add_row("Output Directory", config.output.directory)
        table.add_row("Default Viewport", config.capture.default_viewport)

        console.print(table)


@app.command("validate")
def config_validate():
    """Validate configuration file."""
    try:
        config = load_config()
        console.print("[green]✓[/green] Configuration is valid")

        # Show detected values
        if config.app.base_url:
            console.print(f"  Base URL: {config.app.base_url}")
        if config.proxy.vite_port:
            console.print(f"  Vite Port: {config.proxy.vite_port}")

    except Exception as e:
        console.print(f"[red]✗[/red] Configuration error: {e}")
        raise typer.Exit(1)

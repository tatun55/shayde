"""Main CLI entry point for Shayde."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Optional

import typer
from rich.console import Console
from rich.logging import RichHandler

from shayde import __version__
from shayde.cli import capture, config, docker, scenario, server, test

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format="%(message)s",
    handlers=[RichHandler(rich_tracebacks=True, show_path=False)],
)

console = Console()

app = typer.Typer(
    name="shayde",
    help="Docker Playwright E2E testing and screenshot capture CLI",
    add_completion=True,
    no_args_is_help=True,
)

# Register subcommands
app.add_typer(capture.app, name="capture", help="Screenshot capture commands")
app.add_typer(config.app, name="config", help="Configuration management")
app.add_typer(docker.app, name="docker", help="Docker container management")
app.add_typer(test.app, name="test", help="Playwright E2E test commands")
app.add_typer(scenario.app, name="scenario", help="YAML scenario execution commands")
app.add_typer(server.app, name="server", help="Server management (persistent mode)")


def version_callback(value: bool):
    """Show version and exit."""
    if value:
        console.print(f"Shayde version {__version__}")
        raise typer.Exit()


@app.callback()
def main(
    ctx: typer.Context,
    config_file: Optional[Path] = typer.Option(
        None,
        "--config",
        "-c",
        help="Path to config file",
        exists=True,
        dir_okay=False,
    ),
    verbose: bool = typer.Option(
        False,
        "--verbose",
        "-v",
        help="Enable verbose output",
    ),
    version: bool = typer.Option(
        False,
        "--version",
        "-V",
        callback=version_callback,
        is_eager=True,
        help="Show version and exit",
    ),
):
    """Shayde - Docker Playwright E2E testing and screenshot capture CLI."""
    ctx.ensure_object(dict)
    ctx.obj["config_file"] = config_file
    ctx.obj["verbose"] = verbose

    if verbose:
        logging.getLogger().setLevel(logging.DEBUG)


if __name__ == "__main__":
    app()

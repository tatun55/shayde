"""Docker CLI commands."""

from __future__ import annotations

import typer
from rich.console import Console
from rich.table import Table

from playcap.config.loader import load_config
from playcap.docker.manager import DockerManager

console = Console()
app = typer.Typer(no_args_is_help=True)


@app.command("start")
def docker_start():
    """Start the Playwright Docker container."""
    config = load_config()
    manager = DockerManager(config)

    with console.status("[bold green]Starting container..."):
        success = manager.start()

    if success:
        console.print(f"[green]✓[/green] Container {config.docker.container_name} started")
        console.print(f"  WebSocket: {manager.get_ws_url()}")
    else:
        console.print(f"[red]✗[/red] Failed to start container")
        raise typer.Exit(1)


@app.command("stop")
def docker_stop():
    """Stop the Playwright Docker container."""
    config = load_config()
    manager = DockerManager(config)

    with console.status("[bold green]Stopping container..."):
        success = manager.stop()

    if success:
        console.print(f"[green]✓[/green] Container {config.docker.container_name} stopped")
    else:
        console.print(f"[red]✗[/red] Failed to stop container")
        raise typer.Exit(1)


@app.command("status")
def docker_status():
    """Show Docker container status."""
    config = load_config()
    manager = DockerManager(config)

    status = manager.get_status()

    table = Table(title="Docker Status")
    table.add_column("Property", style="cyan")
    table.add_column("Value", style="green")

    table.add_row("Container Name", status["container_name"])
    table.add_row("Running", "✓ Yes" if status["running"] else "✗ No")
    table.add_row("Docker Daemon", "✓ Running" if status["docker_running"] else "✗ Stopped")
    table.add_row("WebSocket URL", status["ws_url"])
    table.add_row("Playwright Version", status["playwright_version"])
    table.add_row("Image", str(status.get("image", "N/A")))
    table.add_row("Image Built", "✓ Yes" if status.get("image_built") else "✗ No")
    table.add_row("Font Platform", str(status.get("platform", "neutral")))

    console.print(table)


@app.command("build")
def docker_build(
    force: bool = typer.Option(False, "--force", "-f", help="Force rebuild even if image exists"),
):
    """Build the PlayCap Docker image with fonts."""
    config = load_config()
    manager = DockerManager(config)

    if not config.docker.use_custom_image:
        console.print("[yellow]Custom image disabled in config, using official Playwright image[/yellow]")
        return

    with console.status("[bold green]Building image (this may take a few minutes)..."):
        success = manager.build_image(force=force)

    if success:
        console.print(f"[green]✓[/green] Image built successfully")
        console.print(f"  Image: {config.docker.image_name}:latest")
    else:
        console.print(f"[red]✗[/red] Failed to build image")
        raise typer.Exit(1)


@app.command("logs")
def docker_logs(
    tail: int = typer.Option(50, "--tail", "-n", help="Number of lines to show"),
    follow: bool = typer.Option(False, "--follow", "-f", help="Follow log output"),
):
    """Show container logs."""
    config = load_config()
    manager = DockerManager(config)

    if not manager.is_container_running():
        console.print(f"[yellow]Warning:[/yellow] Container {config.docker.container_name} is not running")
        raise typer.Exit(1)

    if follow:
        # Use subprocess for follow mode
        import subprocess
        subprocess.run([
            manager._docker_bin, "logs", "-f", "--tail", str(tail),
            config.docker.container_name,
        ])
    else:
        logs = manager.get_logs(tail=tail)
        console.print(logs)


@app.command("restart")
def docker_restart():
    """Restart the Playwright Docker container."""
    config = load_config()
    manager = DockerManager(config)

    with console.status("[bold green]Restarting container..."):
        manager.stop()
        success = manager.start()

    if success:
        console.print(f"[green]✓[/green] Container {config.docker.container_name} restarted")
    else:
        console.print(f"[red]✗[/red] Failed to restart container")
        raise typer.Exit(1)

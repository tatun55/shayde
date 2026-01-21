"""Server management CLI commands."""

from __future__ import annotations

import os
import signal
import subprocess
import sys
import time
from typing import Optional

import typer
from rich.console import Console

from shayde.server.app import DEFAULT_PORT, PID_FILE, get_pid, is_running
from shayde.server.client import ShaydeClient

console = Console()
app = typer.Typer(help="Server management commands")


@app.command()
def start(
    port: int = typer.Option(DEFAULT_PORT, "--port", "-p", help="Server port"),
    ws_url: str = typer.Option(
        "ws://localhost:3000", "--ws-url", "-w", help="Playwright WebSocket URL"
    ),
    foreground: bool = typer.Option(
        False, "--foreground", "-f", help="Run in foreground (don't daemonize)"
    ),
):
    """Start the Shayde server."""
    if is_running():
        pid = get_pid()
        console.print(f"[yellow]Server already running (PID: {pid})[/yellow]")
        return

    if foreground:
        # Run in foreground
        console.print(f"[green]Starting server on port {port}...[/green]")
        from shayde.server.app import run_server
        run_server(ws_url=ws_url, port=port)
    else:
        # Daemonize
        console.print(f"[green]Starting server in background on port {port}...[/green]")

        # Use subprocess to start server in background
        cmd = [
            sys.executable,
            "-c",
            f"from shayde.server.app import run_server; run_server(ws_url='{ws_url}', port={port})",
        ]

        # Start process detached
        process = subprocess.Popen(
            cmd,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            stdin=subprocess.DEVNULL,
            start_new_session=True,
        )

        # Wait for server to start
        for _ in range(30):
            time.sleep(0.1)
            if ShaydeClient.server_available(port):
                break

        if ShaydeClient.server_available(port):
            pid = get_pid()
            console.print(f"[green]Server started (PID: {pid})[/green]")
            console.print(f"  URL: http://127.0.0.1:{port}")
        else:
            console.print("[red]Failed to start server[/red]")
            raise typer.Exit(1)


@app.command()
def stop():
    """Stop the Shayde server."""
    pid = get_pid()
    if not pid:
        console.print("[yellow]Server is not running[/yellow]")
        return

    # Try graceful shutdown via HTTP first
    if ShaydeClient.server_available():
        try:
            client = ShaydeClient()
            client.stop_sync()
            time.sleep(0.5)
        except Exception:
            pass

    # If still running, send SIGTERM
    pid = get_pid()
    if pid:
        try:
            os.kill(pid, signal.SIGTERM)
            # Wait for process to exit
            for _ in range(50):
                time.sleep(0.1)
                try:
                    os.kill(pid, 0)
                except ProcessLookupError:
                    break
        except ProcessLookupError:
            pass

    # Clean up PID file
    if PID_FILE.exists():
        PID_FILE.unlink()

    console.print("[green]Server stopped[/green]")


@app.command()
def status():
    """Show server status."""
    pid = get_pid()

    if not pid:
        console.print("[yellow]Server is not running[/yellow]")
        return

    console.print(f"[green]Server is running[/green]")
    console.print(f"  PID: {pid}")
    console.print(f"  URL: http://127.0.0.1:{DEFAULT_PORT}")

    # Check health
    if ShaydeClient.server_available():
        try:
            client = ShaydeClient()
            health = client.health_sync()
            console.print(f"  Browser connected: {health.get('browser_connected', False)}")
        except Exception as e:
            console.print(f"  [yellow]Health check failed: {e}[/yellow]")


@app.command()
def restart(
    port: int = typer.Option(DEFAULT_PORT, "--port", "-p", help="Server port"),
    ws_url: str = typer.Option(
        "ws://localhost:3000", "--ws-url", "-w", help="Playwright WebSocket URL"
    ),
):
    """Restart the Shayde server."""
    stop()
    time.sleep(0.5)
    start(port=port, ws_url=ws_url, foreground=False)

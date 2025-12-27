"""Capture CLI commands."""

from __future__ import annotations

import asyncio
from pathlib import Path
from typing import List, Literal, Optional

import typer
from rich.console import Console

from shayde.config.loader import load_config

console = Console()
app = typer.Typer(no_args_is_help=True)

# Platform type for CLI
PlatformOption = Literal["neutral", "mac", "windows"]


@app.command("page")
def capture_page(
    url: str = typer.Argument(..., help="URL or path to capture"),
    name: Optional[str] = typer.Option(
        None, "--name", "-n", help="Custom filename prefix"
    ),
    output: Optional[Path] = typer.Option(
        None, "--output", "-o", help="Output file path"
    ),
    width: Optional[int] = typer.Option(
        None, "--width", "-w", help="Viewport width"
    ),
    height: Optional[int] = typer.Option(
        None, "--height", "-h", help="Viewport height"
    ),
    viewport: Optional[str] = typer.Option(
        None, "--viewport", "-V", help="Named viewport (mobile, tablet, desktop)"
    ),
    platform: Optional[str] = typer.Option(
        None, "--platform", "-P", help="Font platform (neutral, mac, windows)"
    ),
    full_page: bool = typer.Option(
        False, "--full-page", "-f", help="Capture full page"
    ),
    wait_for: Optional[str] = typer.Option(
        None, "--wait-for", help="CSS selector to wait for"
    ),
):
    """Capture a single page screenshot."""
    asyncio.run(_capture_page(
        url=url,
        name=name,
        output=output,
        width=width,
        height=height,
        viewport=viewport,
        platform=platform,
        full_page=full_page,
        wait_for=wait_for,
    ))


async def _capture_page(
    url: str,
    name: Optional[str],
    output: Optional[Path],
    width: Optional[int],
    height: Optional[int],
    viewport: Optional[str],
    platform: Optional[str],
    full_page: bool,
    wait_for: Optional[str],
):
    """Async implementation of capture_page."""
    from shayde.config.schema import ViewportConfig
    from shayde.core.capture import CaptureSession

    config = load_config()

    # Handle custom viewport dimensions
    viewport_config = None
    if width or height:
        viewport_config = ViewportConfig(
            width=width or 1920,
            height=height or 1080,
        )
    elif viewport:
        # Use named viewport
        pass  # Will be resolved in CaptureSession

    platform_label = f" ({platform})" if platform else ""
    with console.status(f"[bold green]Capturing screenshot{platform_label}..."):
        async with CaptureSession(config, platform=platform) as session:
            result = await session.capture(
                url_or_path=url,
                name=name,
                viewport=viewport_config or viewport,
                full_page=full_page,
                wait_for=wait_for,
                output_dir=output.parent if output else None,
            )

    console.print(f"[green]✓[/green] Saved: {result}")


@app.command("batch")
def capture_batch(
    urls: List[str] = typer.Argument(..., help="URLs to capture"),
    output_dir: Optional[Path] = typer.Option(
        None, "--output-dir", "-o", help="Output directory"
    ),
    parallel: int = typer.Option(
        3, "--parallel", "-p", help="Number of parallel captures"
    ),
    viewport: Optional[str] = typer.Option(
        None, "--viewport", "-V", help="Named viewport"
    ),
    platform: Optional[str] = typer.Option(
        None, "--platform", "-P", help="Font platform (neutral, mac, windows)"
    ),
):
    """Capture multiple pages in parallel."""
    asyncio.run(_capture_batch(
        urls=urls,
        output_dir=output_dir,
        parallel=parallel,
        viewport=viewport,
        platform=platform,
    ))


async def _capture_batch(
    urls: List[str],
    output_dir: Optional[Path],
    parallel: int,
    viewport: Optional[str],
    platform: Optional[str],
):
    """Async implementation of capture_batch."""
    import asyncio
    from shayde.core.capture import CaptureSession

    config = load_config()

    async with CaptureSession(config, platform=platform) as session:
        # Create semaphore for parallel limiting
        semaphore = asyncio.Semaphore(parallel)

        async def capture_with_limit(url: str):
            async with semaphore:
                return await session.capture(
                    url_or_path=url,
                    viewport=viewport,
                    output_dir=output_dir,
                )

        with console.status(f"[bold green]Capturing {len(urls)} pages..."):
            results = await asyncio.gather(
                *[capture_with_limit(url) for url in urls],
                return_exceptions=True,
            )

    for url, result in zip(urls, results):
        if isinstance(result, Exception):
            console.print(f"[red]✗[/red] {url}: {result}")
        else:
            console.print(f"[green]✓[/green] {result}")


@app.command("responsive")
def capture_responsive(
    url: str = typer.Argument(..., help="URL to capture"),
    name: Optional[str] = typer.Option(
        None, "--name", "-n", help="Custom filename prefix"
    ),
    viewports: Optional[str] = typer.Option(
        None, "--viewports", help="Comma-separated viewport names"
    ),
):
    """Capture page at multiple viewport sizes."""
    asyncio.run(_capture_responsive(
        url=url,
        name=name,
        viewports=viewports,
    ))


async def _capture_responsive(
    url: str,
    name: Optional[str],
    viewports: Optional[str],
):
    """Async implementation of capture_responsive."""
    from shayde.core.capture import CaptureSession

    config = load_config()

    # Determine which viewports to use
    if viewports:
        viewport_names = [v.strip() for v in viewports.split(",")]
    else:
        viewport_names = list(config.viewports.keys())

    with console.status(f"[bold green]Capturing {len(viewport_names)} viewports..."):
        async with CaptureSession(config) as session:
            results = []
            for vp_name in viewport_names:
                if vp_name not in config.viewports:
                    console.print(f"[yellow]Warning:[/yellow] Unknown viewport: {vp_name}")
                    continue

                result = await session.capture(
                    url_or_path=url,
                    name=name,
                    viewport=vp_name,
                )
                results.append((vp_name, result))

    for vp_name, result in results:
        console.print(f"[green]✓[/green] {vp_name}: {result}")


@app.command("auth")
def capture_auth(
    urls: List[str] = typer.Argument(..., help="URLs to capture after login"),
    email: str = typer.Option(
        ..., "--email", "-e", help="Login email"
    ),
    password: str = typer.Option(
        ..., "--password", "-p", help="Login password", hide_input=True
    ),
    login_url: Optional[str] = typer.Option(
        None, "--login-url", help="Login page URL (default: /login)"
    ),
    viewport: Optional[str] = typer.Option(
        None, "--viewport", "-V", help="Named viewport"
    ),
    platform: Optional[str] = typer.Option(
        None, "--platform", "-P", help="Font platform (neutral, mac, windows)"
    ),
    output_dir: Optional[Path] = typer.Option(
        None, "--output-dir", "-o", help="Output directory"
    ),
):
    """Capture pages after logging in."""
    asyncio.run(_capture_auth(
        urls=urls,
        email=email,
        password=password,
        login_url=login_url,
        viewport=viewport,
        platform=platform,
        output_dir=output_dir,
    ))


async def _capture_auth(
    urls: List[str],
    email: str,
    password: str,
    login_url: Optional[str],
    viewport: Optional[str],
    platform: Optional[str],
    output_dir: Optional[Path],
):
    """Async implementation of capture_auth."""
    from shayde.core.capture import CaptureSession

    config = load_config()

    async with CaptureSession(config, platform=platform) as session:
        # Login first
        with console.status("[bold green]Logging in..."):
            success = await session.login(
                email=email,
                password=password,
                login_url=login_url,
            )

        if not success:
            console.print("[red]✗[/red] Login failed")
            raise typer.Exit(1)

        console.print("[green]✓[/green] Login successful")

        # Capture pages
        with console.status(f"[bold green]Capturing {len(urls)} pages..."):
            results = []
            for url in urls:
                try:
                    result = await session.capture(
                        url_or_path=url,
                        viewport=viewport,
                        output_dir=output_dir,
                    )
                    results.append((url, result, None))
                except Exception as e:
                    results.append((url, None, e))

    for url, result, error in results:
        if error:
            console.print(f"[red]✗[/red] {url}: {error}")
        else:
            console.print(f"[green]✓[/green] {result}")


@app.command("platforms")
def capture_platforms(
    url: str = typer.Argument(..., help="URL or path to capture"),
    name: Optional[str] = typer.Option(
        None, "--name", "-n", help="Custom filename prefix"
    ),
    output_dir: Optional[Path] = typer.Option(
        None, "--output-dir", "-o", help="Output directory"
    ),
    viewport: Optional[str] = typer.Option(
        None, "--viewport", "-V", help="Named viewport"
    ),
    platforms: Optional[str] = typer.Option(
        None, "--platforms", help="Comma-separated platforms (default: mac,windows)"
    ),
):
    """Capture page with multiple platform fonts (Mac and Windows)."""
    asyncio.run(_capture_platforms(
        url=url,
        name=name,
        output_dir=output_dir,
        viewport=viewport,
        platforms=platforms,
    ))


async def _capture_platforms(
    url: str,
    name: Optional[str],
    output_dir: Optional[Path],
    viewport: Optional[str],
    platforms: Optional[str],
):
    """Async implementation of capture_platforms."""
    from shayde.core.capture import CaptureSession

    config = load_config()

    # Determine which platforms to capture
    if platforms:
        platform_list = [p.strip() for p in platforms.split(",")]
    else:
        platform_list = ["mac", "windows"]

    results = []
    for platform in platform_list:
        console.print(f"[bold blue]Capturing with {platform} fonts...[/bold blue]")

        async with CaptureSession(config, platform=platform) as session:
            # Generate name with platform suffix
            capture_name = f"{name}_{platform}" if name else None

            try:
                result = await session.capture(
                    url_or_path=url,
                    name=capture_name,
                    viewport=viewport,
                    output_dir=output_dir,
                    platform_suffix=platform,
                )
                results.append((platform, result, None))
                console.print(f"[green]✓[/green] {platform}: {result}")
            except Exception as e:
                results.append((platform, None, e))
                console.print(f"[red]✗[/red] {platform}: {e}")

    console.print(f"\n[bold]Captured {len([r for r in results if r[2] is None])}/{len(platform_list)} platforms[/bold]")

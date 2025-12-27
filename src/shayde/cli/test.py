"""Test CLI commands for running Playwright E2E tests."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path
from typing import List, Optional

import typer
from rich.console import Console

from shayde.config.loader import load_config
from shayde.docker.manager import DockerManager

console = Console()
app = typer.Typer(no_args_is_help=True)


def _run_before_command(command: str) -> bool:
    """Run the before command on the host."""
    console.print(f"[dim]Running: {command}[/dim]")
    result = subprocess.run(command, shell=True, cwd=Path.cwd())
    return result.returncode == 0


def _build_playwright_args(
    files: List[str],
    headed: bool,
    debug: bool,
    grep: Optional[str],
    workers: int,
    retries: int,
    timeout: int,
    config_file: Optional[str],
    update_snapshots: bool,
) -> List[str]:
    """Build Playwright test command arguments."""
    args = ["npx", "playwright", "test"]

    if files:
        args.extend(files)

    if headed:
        args.append("--headed")

    if debug:
        args.append("--debug")

    if grep:
        args.extend(["--grep", grep])

    if workers > 0:
        args.extend(["--workers", str(workers)])

    if retries > 0:
        args.extend(["--retries", str(retries)])

    if timeout > 0:
        args.extend(["--timeout", str(timeout)])

    if config_file:
        args.extend(["--config", config_file])

    if update_snapshots:
        args.append("--update-snapshots")

    return args


@app.command("run")
def test_run(
    files: Optional[List[str]] = typer.Argument(
        None,
        help="Test files to run (e.g., tests/e2e/login.spec.ts)",
    ),
    headed: bool = typer.Option(
        False,
        "--headed",
        help="Run tests in headed mode (show browser)",
    ),
    debug: bool = typer.Option(
        False,
        "--debug",
        help="Run tests in debug mode",
    ),
    grep: Optional[str] = typer.Option(
        None,
        "--grep",
        "-g",
        help="Only run tests matching this regex",
    ),
    workers: Optional[int] = typer.Option(
        None,
        "--workers",
        "-j",
        help="Number of parallel workers",
    ),
    retries: Optional[int] = typer.Option(
        None,
        "--retries",
        help="Number of retries on failure",
    ),
    update_snapshots: bool = typer.Option(
        False,
        "--update-snapshots",
        "-u",
        help="Update visual snapshots",
    ),
    skip_before: bool = typer.Option(
        False,
        "--skip-before",
        help="Skip running the before command",
    ),
):
    """Run Playwright E2E tests."""
    config = load_config()
    manager = DockerManager(config)

    # Ensure Docker container is running
    if not manager.is_container_running():
        console.print("[yellow]Container not running, starting...[/yellow]")
        with console.status("[bold green]Starting container..."):
            if not manager.start():
                console.print("[red]✗[/red] Failed to start container")
                raise typer.Exit(1)

    # Run before command if configured
    if config.test.before and not skip_before:
        console.print("[bold]Running before command...[/bold]")
        if not _run_before_command(config.test.before):
            console.print("[red]✗[/red] Before command failed")
            raise typer.Exit(1)
        console.print("[green]✓[/green] Before command completed")
        console.print()

    # Build test command
    test_files = list(files) if files else []
    playwright_args = _build_playwright_args(
        files=test_files,
        headed=headed,
        debug=debug,
        grep=grep,
        workers=workers if workers is not None else config.test.workers,
        retries=retries if retries is not None else config.test.retries,
        timeout=config.test.timeout,
        config_file=config.test.config_file,
        update_snapshots=update_snapshots,
    )

    # Get test directory
    test_dir = Path.cwd() / config.test.directory
    if not test_dir.exists():
        console.print(f"[yellow]Warning:[/yellow] Test directory {test_dir} does not exist")
        console.print(f"Create it with: mkdir -p {config.test.directory}")
        raise typer.Exit(1)

    # Run tests using npx playwright directly (tests run on host, browser in container)
    console.print(f"[bold]Running Playwright tests...[/bold]")
    console.print(f"[dim]Directory: {config.test.directory}[/dim]")
    console.print(f"[dim]Command: {' '.join(playwright_args)}[/dim]")
    console.print()

    # Set environment for Playwright to connect to Docker container
    import os
    env = os.environ.copy()
    env["PW_TEST_CONNECT_WS_ENDPOINT"] = manager.get_ws_url()

    # Run playwright test
    result = subprocess.run(
        playwright_args,
        cwd=Path.cwd(),
        env=env,
    )

    if result.returncode == 0:
        console.print()
        console.print("[green]✓[/green] All tests passed")
    else:
        console.print()
        console.print(f"[red]✗[/red] Tests failed (exit code: {result.returncode})")
        raise typer.Exit(result.returncode)


@app.command("list")
def test_list():
    """List available test files."""
    config = load_config()
    test_dir = Path.cwd() / config.test.directory

    if not test_dir.exists():
        console.print(f"[yellow]Test directory {test_dir} does not exist[/yellow]")
        raise typer.Exit(1)

    # Find test files
    test_files = list(test_dir.glob("**/*.spec.ts")) + list(test_dir.glob("**/*.test.ts"))

    if not test_files:
        console.print(f"[yellow]No test files found in {test_dir}[/yellow]")
        return

    console.print(f"[bold]Test files in {config.test.directory}:[/bold]")
    for f in sorted(test_files):
        relative = f.relative_to(Path.cwd())
        console.print(f"  {relative}")


@app.command("init")
def test_init():
    """Initialize Playwright test setup."""
    config = load_config()
    test_dir = Path.cwd() / config.test.directory

    # Create test directory
    if not test_dir.exists():
        test_dir.mkdir(parents=True)
        console.print(f"[green]✓[/green] Created {config.test.directory}/")

    # Create playwright.config.ts if it doesn't exist
    playwright_config = Path.cwd() / "playwright.config.ts"
    if not playwright_config.exists():
        playwright_config.write_text('''import { defineConfig, devices } from '@playwright/test';

export default defineConfig({
  testDir: './tests/e2e',
  fullyParallel: true,
  forbidOnly: !!process.env.CI,
  retries: process.env.CI ? 2 : 0,
  workers: process.env.CI ? 1 : undefined,
  reporter: 'html',
  use: {
    baseURL: process.env.APP_URL || 'http://localhost',
    trace: 'on-first-retry',
    // Connect to Docker container
    connectOptions: {
      wsEndpoint: process.env.PW_TEST_CONNECT_WS_ENDPOINT || 'ws://localhost:3000',
    },
  },
  projects: [
    {
      name: 'chromium',
      use: { ...devices['Desktop Chrome'] },
    },
  ],
});
''')
        console.print("[green]✓[/green] Created playwright.config.ts")

    # Create example test file
    example_test = test_dir / "example.spec.ts"
    if not example_test.exists():
        example_test.write_text('''import { test, expect } from '@playwright/test';

test('has title', async ({ page }) => {
  await page.goto('/');
  await expect(page).toHaveTitle(/./);
});

test('can navigate', async ({ page }) => {
  await page.goto('/');
  // Add your navigation tests here
});
''')
        console.print(f"[green]✓[/green] Created {config.test.directory}/example.spec.ts")

    console.print()
    console.print("[bold]Next steps:[/bold]")
    console.print("  1. npm install -D @playwright/test")
    console.print("  2. shayde docker start")
    console.print("  3. shayde test run")

"""Scenario CLI commands."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Optional

import typer
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.tree import Tree

console = Console()
app = typer.Typer(no_args_is_help=True)

# Session subgroup for step-by-step execution
session_app = typer.Typer(no_args_is_help=True, help="Step-by-step scenario execution")
app.add_typer(session_app, name="session")


@app.command("parse")
def parse_scenario(
    file: Path = typer.Argument(..., help="Path to scenario YAML file", exists=True),
    validate: bool = typer.Option(
        False, "--validate", "-v", help="Validate scenario structure"
    ),
    output_json: bool = typer.Option(
        False, "--json", "-j", help="Output as JSON"
    ),
):
    """Parse and display scenario structure."""
    from shayde.core.scenario.parser import ScenarioParser

    parser = ScenarioParser()

    try:
        scenario = parser.parse(file)
    except Exception as e:
        console.print(f"[red]Error parsing scenario:[/red] {e}")
        raise typer.Exit(1)

    if validate:
        is_valid, errors, warnings = parser.validate(scenario)

        if errors:
            console.print("[red]Validation Errors:[/red]")
            for error in errors:
                console.print(f"  [red]✗[/red] {error}")

        if warnings:
            console.print("[yellow]Warnings:[/yellow]")
            for warning in warnings:
                console.print(f"  [yellow]![/yellow] {warning}")

        if is_valid:
            console.print("[green]✓ Scenario is valid[/green]")
        else:
            raise typer.Exit(1)

    if output_json:
        console.print_json(json.dumps(scenario.to_dict(), ensure_ascii=False, indent=2))
    else:
        _print_scenario_summary(scenario)


@app.command("list")
def list_steps(
    file: Path = typer.Argument(..., help="Path to scenario YAML file", exists=True),
    part: Optional[int] = typer.Option(
        None, "--part", "-p", help="Show only specific part"
    ),
):
    """List all steps in scenario."""
    from shayde.core.scenario.parser import ScenarioParser

    parser = ScenarioParser()

    try:
        scenario = parser.parse(file)
    except Exception as e:
        console.print(f"[red]Error parsing scenario:[/red] {e}")
        raise typer.Exit(1)

    _print_step_list(scenario, part_filter=part)


def _print_scenario_summary(scenario) -> None:
    """Print scenario summary."""
    # Header
    console.print()
    console.print(Panel(
        f"[bold]{scenario.meta.title}[/bold]\n"
        f"ID: {scenario.meta.id} | Priority: {scenario.meta.priority.value} | "
        f"Est. Time: {scenario.meta.estimated_time or '?'}min",
        title="Scenario",
        border_style="blue",
    ))

    # Prerequisites
    if scenario.prerequisites:
        console.print("\n[bold]Prerequisites:[/bold]")
        for prereq in scenario.prerequisites:
            console.print(f"  • {prereq}")

    # Coverage
    if scenario.coverage:
        console.print("\n[bold]Coverage:[/bold]")
        for cov in scenario.coverage:
            status_icon = "○" if cov.status.value == "complete" else "△"
            console.print(f"  {status_icon} {cov.name}")

    # Accounts
    if scenario.accounts:
        console.print("\n[bold]Accounts:[/bold]")
        for key, acc in scenario.accounts.items():
            console.print(f"  [{key}] {acc.email} ({acc.role or 'N/A'})")

    # Summary
    console.print()
    table = Table(show_header=False, box=None)
    table.add_column("Label", style="dim")
    table.add_column("Value")
    table.add_row("Parts", str(len(scenario.steps)))
    table.add_row("Steps", str(scenario.total_steps))
    table.add_row("Screenshots", str(scenario.total_screenshots))
    console.print(table)


def _print_step_list(scenario, part_filter: Optional[int] = None) -> None:
    """Print step list."""
    console.print()
    console.print(f"[bold]{scenario.meta.id}:[/bold] {scenario.meta.title}")
    console.print("━" * 50)

    total_steps = 0
    total_screenshots = 0

    for part in scenario.steps:
        if part_filter is not None and part.part != part_filter:
            continue

        account_info = f"(account: {part.account or 'none'})"
        console.print(f"\n[bold blue]Part {part.part}:[/bold blue] {part.title} [dim]{account_info}[/dim]")

        for step in part.items:
            screenshot_icon = " 📸" if step.has_screenshot else ""
            action_type = _get_action_type(step.action)
            action_hint = f" [dim]({action_type})[/dim]" if action_type else ""

            console.print(f"  [{step.id}] {step.desc}{action_hint}{screenshot_icon}")
            total_steps += 1
            if step.has_screenshot:
                total_screenshots += 1

    console.print()
    console.print(f"[dim]Total: {total_steps} steps, {total_screenshots} screenshots[/dim]")


def _get_action_type(action) -> Optional[str]:
    """Get action type hint."""
    if action is None:
        return "verify"
    if isinstance(action, dict):
        if "goto" in action:
            return "goto"
        if "fill" in action:
            return "fill"
        if "click" in action:
            return "click"
        if "select" in action:
            return "select"
        if "upload" in action:
            return "upload"
        if "login" in action:
            return "login"
        if "logout" in action:
            return "logout"
    if isinstance(action, list):
        return "multi"
    return None


@app.command("run")
def run_scenario_cmd(
    file: Path = typer.Argument(..., help="Path to scenario YAML file", exists=True),
    output_dir: Optional[Path] = typer.Option(
        None, "--output", "-o", help="Output directory for screenshots"
    ),
    part: Optional[int] = typer.Option(
        None, "--part", "-p", help="Run only specific part"
    ),
    stop_on_error: bool = typer.Option(
        False, "--stop-on-error", "-e", help="Stop execution on first error"
    ),
    base_url: Optional[str] = typer.Option(
        None, "--base-url", "-b", help="Base URL override"
    ),
    video: bool = typer.Option(
        True, "--video/--no-video", "-v", help="Record video of scenario execution (default: on)"
    ),
):
    """Run all steps in scenario."""
    import asyncio
    from shayde.core.scenario.runner import run_scenario
    from shayde.core.scenario.models import StepStatus

    console.print(f"\n[bold blue]Running scenario:[/bold blue] {file.name}")

    try:
        session = asyncio.run(run_scenario(
            scenario_path=file,
            output_dir=output_dir,
            base_url=base_url,
            stop_on_error=stop_on_error,
            part_filter=part,
            record_video=video,
        ))

        # Print summary
        result = session.result
        console.print()
        console.print("━" * 50)

        status_icon = "✓" if result.status == StepStatus.PASSED else "✗"
        status_color = "green" if result.status == StepStatus.PASSED else "red"
        console.print(f"[{status_color}]{status_icon} {result.status.value.upper()}[/{status_color}]")

        console.print(f"  Total: {result.total_steps} steps")
        console.print(f"  Passed: [green]{result.passed_count}[/green]")
        if result.failed_count > 0:
            console.print(f"  Failed: [red]{result.failed_count}[/red]")
        if result.skipped_count > 0:
            console.print(f"  Skipped: [yellow]{result.skipped_count}[/yellow]")
        console.print(f"  Duration: {result.duration_ms / 1000:.1f}s")
        console.print(f"  Output: {result.output_dir}")
        if result.video_path:
            console.print(f"  🎬 Video: {result.video_path}")

        if result.status == StepStatus.FAILED:
            raise typer.Exit(1)

    except Exception as e:
        console.print(f"[red]Error running scenario:[/red] {e}")
        raise typer.Exit(1)


@app.command("step")
def run_step_cmd(
    file: Path = typer.Argument(..., help="Path to scenario YAML file", exists=True),
    step_id: str = typer.Argument(..., help="Step ID to execute (e.g., '1-1')"),
    output_dir: Optional[Path] = typer.Option(
        None, "--output", "-o", help="Output directory for screenshot"
    ),
    base_url: Optional[str] = typer.Option(
        None, "--base-url", "-b", help="Base URL override"
    ),
):
    """Execute a single step."""
    import asyncio
    from shayde.core.scenario.runner import run_single_step
    from shayde.core.scenario.models import StepStatus

    console.print(f"\n[bold blue]Running step:[/bold blue] {step_id}")

    try:
        result = asyncio.run(run_single_step(
            scenario_path=file,
            step_id=step_id,
            output_dir=output_dir,
            base_url=base_url,
        ))

        if result is None:
            console.print(f"[red]Step not found:[/red] {step_id}")
            raise typer.Exit(1)

        # Print result
        console.print()
        status_icon = "✓" if result.status == StepStatus.PASSED else "✗"
        status_color = "green" if result.status == StepStatus.PASSED else "red"
        console.print(f"[{status_color}]{status_icon} {result.desc}[/{status_color}]")

        if result.screenshot:
            console.print(f"  📸 {result.screenshot}")

        if result.error:
            console.print(f"  [red]Error: {result.error}[/red]")

        console.print(f"  Duration: {result.duration_ms}ms")

        if result.status == StepStatus.FAILED:
            raise typer.Exit(1)

    except Exception as e:
        console.print(f"[red]Error running step:[/red] {e}")
        raise typer.Exit(1)


@app.command("report")
def generate_report_cmd(
    results_dir: Path = typer.Argument(
        ..., help="Directory containing results.json", exists=True
    ),
    output: Optional[Path] = typer.Option(
        None, "--output", "-o", help="Output file path (default: report.md in results_dir)"
    ),
):
    """Generate Markdown report from execution results."""
    from shayde.core.scenario.reporter import generate_report

    try:
        report_path = generate_report(results_dir, output)
        console.print(f"[green]✓ Report generated:[/green] {report_path}")

    except FileNotFoundError as e:
        console.print(f"[red]Error:[/red] {e}")
        raise typer.Exit(1)
    except Exception as e:
        console.print(f"[red]Error generating report:[/red] {e}")
        raise typer.Exit(1)


# =============================================================================
# Session Commands - Step-by-step execution
# =============================================================================


@session_app.command("start")
def session_start(
    file: Path = typer.Argument(..., help="Path to scenario YAML file", exists=True),
    output_dir: Optional[Path] = typer.Option(
        None, "--output", "-o", help="Output directory for screenshots"
    ),
    base_url: Optional[str] = typer.Option(
        None, "--base-url", "-b", help="Base URL override"
    ),
    video: bool = typer.Option(
        True, "--video/--no-video", help="Record video (default: on)"
    ),
    part: int = typer.Option(
        1, "--part", "-p", help="Part number to start from"
    ),
    json_output: bool = typer.Option(
        False, "--json", "-j", help="Output as JSON"
    ),
):
    """Start a new step-by-step session.

    Creates a new session for interactive step-by-step execution.
    Returns a session ID that can be used with other session commands.
    """
    import asyncio
    from shayde.core.scenario.session_manager import SessionManager

    try:
        info = asyncio.run(SessionManager.create(
            yaml_path=file,
            output_dir=output_dir,
            base_url=base_url,
            record_video=video,
            start_part=part,
        ))

        if json_output:
            console.print_json(json.dumps(info.to_dict(), ensure_ascii=False))
        else:
            console.print(f"\n[bold green]Session started:[/bold green] {info.session_id}")
            console.print(f"  Scenario: {info.scenario_title}")
            console.print(f"  Parts: {info.total_parts}")
            console.print(f"  Steps: {info.total_steps}")
            console.print(f"\nRun steps with: [bold]shayde scenario session step {info.session_id}[/bold]")

    except Exception as e:
        console.print(f"[red]Error starting session:[/red] {e}")
        raise typer.Exit(1)


@session_app.command("step")
def session_step(
    session_id: str = typer.Argument(..., help="Session ID"),
    retry: bool = typer.Option(
        False, "--retry", "-r", help="Retry current step"
    ),
    skip: bool = typer.Option(
        False, "--skip", "-s", help="Skip current step"
    ),
    json_output: bool = typer.Option(
        False, "--json", "-j", help="Output as JSON"
    ),
):
    """Execute the next step in a session.

    Runs the next step and returns the result.
    Use --retry to re-run the current step.
    Use --skip to skip the current step.
    """
    import asyncio
    from shayde.core.scenario.session_manager import SessionManager
    from shayde.core.scenario.models import StepStatus

    try:
        result = asyncio.run(SessionManager.execute_next_step(
            session_id=session_id,
            retry=retry,
            skip=skip,
        ))

        if json_output:
            console.print_json(json.dumps(result.to_dict(), ensure_ascii=False))
        else:
            # Status icon
            status = result.result.status
            if status == StepStatus.PASSED:
                icon = "[green]✓[/green]"
            elif status == StepStatus.FAILED:
                icon = "[red]✗[/red]"
            else:
                icon = "[yellow]○[/yellow]"

            console.print(f"\n{icon} [bold]Step {result.step_id}:[/bold] {result.step_desc}")
            console.print(f"  Part: {result.part_num} - {result.part_title}")
            console.print(f"  Duration: {result.result.duration_ms}ms")

            if result.result.screenshot:
                console.print(f"  📸 {result.result.screenshot}")

            if result.result.error:
                console.print(f"  [red]Error: {result.result.error}[/red]")

            # Next step info
            if result.is_completed:
                console.print(f"\n[bold green]✓ Scenario completed![/bold green]")
                console.print(f"End session with: [bold]shayde scenario session end {session_id}[/bold]")
            else:
                console.print(f"\n  Next: Part {result.next_part}, Step {result.next_step}")
                if result.is_account_change:
                    console.print("  [yellow]Account switch will occur[/yellow]")

    except ValueError as e:
        console.print(f"[red]Error:[/red] {e}")
        raise typer.Exit(1)
    except Exception as e:
        console.print(f"[red]Error executing step:[/red] {e}")
        raise typer.Exit(1)


@session_app.command("end")
def session_end(
    session_id: str = typer.Argument(..., help="Session ID"),
    json_output: bool = typer.Option(
        False, "--json", "-j", help="Output as JSON"
    ),
):
    """End a session and save results.

    Closes the browser context, saves the video, and returns final results.
    """
    import asyncio
    from shayde.core.scenario.session_manager import SessionManager

    try:
        result = asyncio.run(SessionManager.end(session_id))

        if json_output:
            console.print_json(json.dumps(result.to_dict(), ensure_ascii=False))
        else:
            status_color = "green" if result.status == "passed" else "red" if result.status == "failed" else "yellow"
            console.print(f"\n[bold {status_color}]Session ended: {result.status.upper()}[/bold {status_color}]")
            console.print(f"  Total: {result.total_steps} steps")
            console.print(f"  Passed: [green]{result.passed}[/green]")
            if result.failed > 0:
                console.print(f"  Failed: [red]{result.failed}[/red]")
            if result.skipped > 0:
                console.print(f"  Skipped: [yellow]{result.skipped}[/yellow]")
            console.print(f"  Duration: {result.duration_ms / 1000:.1f}s")
            if result.results_path:
                console.print(f"  Results: {result.results_path}")
            if result.video_path:
                console.print(f"  🎬 Video: {result.video_path}")

    except ValueError as e:
        console.print(f"[red]Error:[/red] {e}")
        raise typer.Exit(1)
    except Exception as e:
        console.print(f"[red]Error ending session:[/red] {e}")
        raise typer.Exit(1)


@session_app.command("list")
def session_list(
    json_output: bool = typer.Option(
        False, "--json", "-j", help="Output as JSON"
    ),
):
    """List active sessions."""
    from shayde.core.scenario.session_manager import SessionManager

    sessions = SessionManager.list_sessions()

    if json_output:
        console.print_json(json.dumps([s.to_dict() for s in sessions], ensure_ascii=False))
    else:
        if not sessions:
            console.print("[dim]No active sessions[/dim]")
            return

        table = Table(title="Active Sessions")
        table.add_column("Session ID", style="bold")
        table.add_column("Scenario")
        table.add_column("Part")
        table.add_column("Step")
        table.add_column("Status")
        table.add_column("Created")

        for s in sessions:
            table.add_row(
                s.session_id,
                s.scenario_id,
                str(s.current_part),
                str(s.current_step_index),
                s.status,
                s.created_at.strftime("%H:%M:%S"),
            )

        console.print(table)


@session_app.command("info")
def session_info(
    session_id: str = typer.Argument(..., help="Session ID"),
    json_output: bool = typer.Option(
        False, "--json", "-j", help="Output as JSON"
    ),
):
    """Get session details."""
    from shayde.core.scenario.session_manager import SessionManager

    info = SessionManager.get_session(session_id)

    if info is None:
        console.print(f"[red]Session not found:[/red] {session_id}")
        raise typer.Exit(1)

    if json_output:
        console.print_json(json.dumps(info.to_dict(), ensure_ascii=False))
    else:
        console.print(f"\n[bold]Session {info.session_id}[/bold]")
        console.print(f"  Scenario: {info.scenario_title} ({info.scenario_id})")
        console.print(f"  Status: {info.status}")
        console.print(f"  Current: Part {info.current_part}, Step {info.current_step_index}")
        console.print(f"  Account: {info.current_account or 'none'}")
        console.print(f"  Progress: {info.current_step_index}/{info.total_steps} steps")
        console.print(f"  Created: {info.created_at.strftime('%Y-%m-%d %H:%M:%S')}")

"""Session manager for step-by-step scenario execution."""

from __future__ import annotations

import logging
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING, Dict, Optional

if TYPE_CHECKING:
    from playwright.async_api import Browser

from shayde.core.browser import BrowserManager
from shayde.core.scenario.models import (
    SessionEndResult,
    SessionInfo,
    StepExecutionResult,
    StepResult,
    StepStatus,
)
from shayde.core.scenario.parser import Part, Scenario, Step, parse_scenario
from shayde.core.scenario.runner import ScenarioRunner
from shayde.core.scenario.session import ScenarioSession
from shayde.config.loader import load_config

logger = logging.getLogger(__name__)


@dataclass
class ManagedSession:
    """Internal representation of a managed step-by-step session."""

    id: str
    scenario: Scenario
    session: ScenarioSession
    runner: ScenarioRunner
    browser_manager: BrowserManager
    current_part_index: int = 0
    current_step_index: int = 0
    status: str = "initialized"  # initialized, running, paused, completed, error
    created_at: datetime = field(default_factory=datetime.now)
    executed_steps: int = 0
    passed_steps: int = 0
    failed_steps: int = 0
    skipped_steps: int = 0

    def get_current_part(self) -> Optional[Part]:
        """Get current part."""
        if self.current_part_index < len(self.scenario.steps):
            return self.scenario.steps[self.current_part_index]
        return None

    def get_current_step(self) -> Optional[Step]:
        """Get current step."""
        part = self.get_current_part()
        if part and self.current_step_index < len(part.items):
            return part.items[self.current_step_index]
        return None

    def get_total_steps(self) -> int:
        """Get total number of steps in scenario."""
        return sum(len(p.items) for p in self.scenario.steps)

    def to_info(self) -> SessionInfo:
        """Convert to SessionInfo for external representation."""
        return SessionInfo(
            session_id=self.id,
            scenario_id=self.scenario.meta.id,
            scenario_title=self.scenario.meta.title,
            total_parts=len(self.scenario.steps),
            total_steps=self.get_total_steps(),
            current_part=self.current_part_index + 1,
            current_step_index=self.current_step_index,
            current_account=self.session.current_account,
            status=self.status,
            created_at=self.created_at,
        )


class SessionManager:
    """Manages step-by-step scenario execution sessions.

    This class provides APIs for:
    - Creating new sessions (initializing browser and scenario)
    - Executing individual steps
    - Retrying or skipping steps
    - Ending sessions and collecting results
    """

    _sessions: Dict[str, ManagedSession] = {}

    @classmethod
    async def create(
        cls,
        yaml_path: Path,
        output_dir: Optional[Path] = None,
        base_url: Optional[str] = None,
        record_video: bool = True,
        start_part: int = 1,
    ) -> SessionInfo:
        """Create a new step-by-step session.

        Args:
            yaml_path: Path to scenario YAML file
            output_dir: Output directory for screenshots/video
            base_url: Base URL override
            record_video: Whether to record video
            start_part: Part number to start from (1-indexed)

        Returns:
            SessionInfo with session details
        """
        session_id = str(uuid.uuid4())[:8]
        logger.info(f"Creating session {session_id} for {yaml_path}")

        # Parse scenario
        scenario = parse_scenario(yaml_path)

        # Load config and connect browser
        config = load_config()
        browser_manager = BrowserManager(config)
        await browser_manager.connect()
        browser = browser_manager.browser

        if not browser:
            raise RuntimeError("Failed to connect to browser")

        # Determine output directory
        if output_dir is None:
            output_dir = Path(f"screenshots/{scenario.meta.id}_{scenario.meta.title}")

        # Create scenario session
        scenario_session = ScenarioSession(
            scenario=scenario,
            output_dir=output_dir,
            browser=browser,
            base_url=base_url,
            record_video=record_video,
        )

        # Initialize session (creates browser context)
        await scenario_session.setup()

        # Create runner
        runner = ScenarioRunner(scenario_session)

        # Create managed session
        managed = ManagedSession(
            id=session_id,
            scenario=scenario,
            session=scenario_session,
            runner=runner,
            browser_manager=browser_manager,
            current_part_index=start_part - 1,
            current_step_index=0,
            status="initialized",
        )

        cls._sessions[session_id] = managed
        logger.info(f"Session {session_id} created successfully")

        return managed.to_info()

    @classmethod
    async def execute_next_step(
        cls,
        session_id: str,
        retry: bool = False,
        skip: bool = False,
    ) -> StepExecutionResult:
        """Execute the next step in the session.

        Args:
            session_id: Session ID
            retry: If True, retry the current step instead of advancing
            skip: If True, skip the current step

        Returns:
            StepExecutionResult with step result and next step info
        """
        managed = cls._sessions.get(session_id)
        if not managed:
            raise ValueError(f"Session not found: {session_id}")

        if managed.status == "completed":
            raise ValueError(f"Session already completed: {session_id}")

        managed.status = "running"

        # Get current part and step
        part = managed.get_current_part()
        step = managed.get_current_step()

        if not part or not step:
            raise ValueError(f"No more steps in session: {session_id}")

        # Start part if needed (for result tracking)
        if managed.current_step_index == 0:
            managed.session.start_part(part)

        # Handle account switching
        if part.account != managed.session.current_account:
            success = await managed.session.switch_account(part.account)
            if not success and part.account:
                logger.error(f"Failed to switch to account: {part.account}")

        # Execute step
        if skip:
            result = StepResult(
                step_id=step.id,
                desc=step.desc,
                status=StepStatus.SKIPPED,
                duration_ms=0,
            )
            managed.session.record_step_result(result)
            managed.skipped_steps += 1
        else:
            result = await managed.runner.run_step(step, part)
            managed.executed_steps += 1
            if result.status == StepStatus.PASSED:
                managed.passed_steps += 1
            elif result.status == StepStatus.FAILED:
                managed.failed_steps += 1

        # Determine next step
        is_completed = False
        is_part_change = False
        is_account_change = False
        next_part_num = managed.current_part_index + 1
        next_step_id: Optional[str] = None

        if not retry:
            managed.current_step_index += 1

            # Check if part is complete
            if managed.current_step_index >= len(part.items):
                managed.session.finish_part()
                managed.current_step_index = 0
                managed.current_part_index += 1
                is_part_change = True

                # Check if scenario is complete
                if managed.current_part_index >= len(managed.scenario.steps):
                    is_completed = True
                    managed.status = "completed"
                    next_part_num = managed.current_part_index + 1
                else:
                    next_part = managed.scenario.steps[managed.current_part_index]
                    next_part_num = managed.current_part_index + 1
                    if next_part.account != part.account:
                        is_account_change = True
                    if next_part.items:
                        next_step_id = next_part.items[0].id
            else:
                next_step_id = part.items[managed.current_step_index].id
        else:
            # Retry - keep same position
            next_step_id = step.id

        if not is_completed:
            managed.status = "paused"

        return StepExecutionResult(
            session_id=session_id,
            step_id=step.id,
            step_desc=step.desc,
            part_num=part.part,
            part_title=part.title,
            result=result,
            is_completed=is_completed,
            is_part_change=is_part_change,
            is_account_change=is_account_change,
            next_part=next_part_num if not is_completed else None,
            next_step=next_step_id,
        )

    @classmethod
    async def end(cls, session_id: str) -> SessionEndResult:
        """End a session and cleanup resources.

        Args:
            session_id: Session ID

        Returns:
            SessionEndResult with final results
        """
        managed = cls._sessions.pop(session_id, None)
        if not managed:
            raise ValueError(f"Session not found: {session_id}")

        logger.info(f"Ending session {session_id}")

        # Finish scenario if not already done
        if managed.status != "completed":
            managed.session.finish_scenario()

        # Save results
        results_path = managed.session.save_results()

        # Get video path if recording
        video_path: Optional[Path] = None
        if managed.session.record_video and managed.session.context:
            try:
                # Close context to finalize video
                await managed.session.teardown()
                video_path = managed.session.video_path
            except Exception as e:
                logger.error(f"Error saving video: {e}")

        # Calculate totals
        total_steps = managed.get_total_steps()
        duration_ms = 0
        if managed.session.result:
            duration_ms = managed.session.result.duration_ms

        # Determine final status
        if managed.failed_steps > 0:
            final_status = "failed"
        elif managed.executed_steps == total_steps:
            final_status = "passed"
        else:
            final_status = "partial"

        return SessionEndResult(
            session_id=session_id,
            status=final_status,
            total_steps=total_steps,
            passed=managed.passed_steps,
            failed=managed.failed_steps,
            skipped=managed.skipped_steps,
            duration_ms=duration_ms,
            results_path=results_path,
            video_path=video_path,
        )

    @classmethod
    def list_sessions(cls) -> list[SessionInfo]:
        """List all active sessions.

        Returns:
            List of SessionInfo
        """
        return [m.to_info() for m in cls._sessions.values()]

    @classmethod
    def get_session(cls, session_id: str) -> Optional[SessionInfo]:
        """Get session info by ID.

        Args:
            session_id: Session ID

        Returns:
            SessionInfo or None if not found
        """
        managed = cls._sessions.get(session_id)
        return managed.to_info() if managed else None

    @classmethod
    async def cleanup_all(cls) -> None:
        """Cleanup all active sessions."""
        session_ids = list(cls._sessions.keys())
        for session_id in session_ids:
            try:
                await cls.end(session_id)
            except Exception as e:
                logger.error(f"Error cleaning up session {session_id}: {e}")

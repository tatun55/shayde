"""Data models for scenario execution."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any, Optional


class StepStatus(str, Enum):
    """Step execution status."""
    PENDING = "pending"
    RUNNING = "running"
    PASSED = "passed"
    FAILED = "failed"
    SKIPPED = "skipped"


class Priority(str, Enum):
    """Scenario priority."""
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class CoverageStatus(str, Enum):
    """Coverage status."""
    COMPLETE = "complete"
    PARTIAL = "partial"


@dataclass
class AssertionResult:
    """Result of a single assertion."""
    type: str
    expected: Any
    actual: Any
    passed: bool
    message: Optional[str] = None


@dataclass
class StepResult:
    """Result of a single step execution."""
    step_id: str
    desc: str
    status: StepStatus
    screenshot: Optional[Path] = None
    duration_ms: int = 0
    assertions: list[AssertionResult] = field(default_factory=list)
    error: Optional[str] = None
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None

    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization."""
        return {
            "id": self.step_id,
            "desc": self.desc,
            "status": self.status.value,
            "screenshot": str(self.screenshot) if self.screenshot else None,
            "duration_ms": self.duration_ms,
            "assertions": [
                {
                    "type": a.type,
                    "expected": a.expected,
                    "actual": a.actual,
                    "passed": a.passed,
                    "message": a.message,
                }
                for a in self.assertions
            ],
            "error": self.error,
        }


@dataclass
class PartResult:
    """Result of a part execution."""
    part: int
    title: str
    status: StepStatus
    steps: list[StepResult] = field(default_factory=list)

    @property
    def passed_count(self) -> int:
        return sum(1 for s in self.steps if s.status == StepStatus.PASSED)

    @property
    def failed_count(self) -> int:
        return sum(1 for s in self.steps if s.status == StepStatus.FAILED)

    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization."""
        return {
            "part": self.part,
            "title": self.title,
            "status": self.status.value,
            "steps": [s.to_dict() for s in self.steps],
        }


@dataclass
class ScenarioResult:
    """Result of a scenario execution."""
    scenario_id: str
    title: str
    status: StepStatus
    parts: list[PartResult] = field(default_factory=list)
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    output_dir: Optional[Path] = None
    video_path: Optional[Path] = None

    @property
    def total_steps(self) -> int:
        return sum(len(p.steps) for p in self.parts)

    @property
    def passed_count(self) -> int:
        return sum(p.passed_count for p in self.parts)

    @property
    def failed_count(self) -> int:
        return sum(p.failed_count for p in self.parts)

    @property
    def skipped_count(self) -> int:
        return sum(
            1 for p in self.parts for s in p.steps if s.status == StepStatus.SKIPPED
        )

    @property
    def duration_ms(self) -> int:
        if self.started_at and self.completed_at:
            return int((self.completed_at - self.started_at).total_seconds() * 1000)
        return sum(s.duration_ms for p in self.parts for s in p.steps)

    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization."""
        return {
            "scenario_id": self.scenario_id,
            "title": self.title,
            "status": self.status.value,
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "output_dir": str(self.output_dir) if self.output_dir else None,
            "video_path": str(self.video_path) if self.video_path else None,
            "parts": [p.to_dict() for p in self.parts],
            "summary": {
                "total_steps": self.total_steps,
                "passed": self.passed_count,
                "failed": self.failed_count,
                "skipped": self.skipped_count,
                "duration_ms": self.duration_ms,
            },
        }


# --- Step-by-step execution models ---


@dataclass
class StepExecutionResult:
    """Result of a single step execution in step-by-step mode."""

    session_id: str
    step_id: str
    step_desc: str
    part_num: int
    part_title: str
    result: StepResult
    is_completed: bool
    is_part_change: bool
    is_account_change: bool
    next_part: Optional[int]
    next_step: Optional[str]

    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization."""
        return {
            "session_id": self.session_id,
            "step": {
                "id": self.step_id,
                "desc": self.step_desc,
                "part": self.part_num,
                "part_title": self.part_title,
            },
            "result": {
                "status": self.result.status.value,
                "duration_ms": self.result.duration_ms,
                "screenshot": str(self.result.screenshot) if self.result.screenshot else None,
                "assertions": [
                    {
                        "type": a.type,
                        "expected": a.expected,
                        "passed": a.passed,
                    }
                    for a in self.result.assertions
                ],
                "error": self.result.error,
            },
            "next": {
                "part": self.next_part,
                "step": self.next_step,
                "is_part_change": self.is_part_change,
                "is_account_change": self.is_account_change,
                "is_completed": self.is_completed,
            },
        }


@dataclass
class SessionEndResult:
    """Result of ending a step-by-step session."""

    session_id: str
    status: str
    total_steps: int
    passed: int
    failed: int
    skipped: int
    duration_ms: int
    results_path: Optional[Path]
    video_path: Optional[Path]

    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization."""
        return {
            "session_id": self.session_id,
            "result": {
                "status": self.status,
                "total_steps": self.total_steps,
                "passed": self.passed,
                "failed": self.failed,
                "skipped": self.skipped,
                "duration_ms": self.duration_ms,
            },
            "output": {
                "results_json": str(self.results_path) if self.results_path else None,
                "video": str(self.video_path) if self.video_path else None,
            },
        }


@dataclass
class SessionInfo:
    """Information about an active step-by-step session."""

    session_id: str
    scenario_id: str
    scenario_title: str
    total_parts: int
    total_steps: int
    current_part: int
    current_step_index: int
    current_account: Optional[str]
    status: str
    created_at: datetime

    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization."""
        return {
            "session_id": self.session_id,
            "scenario": {
                "id": self.scenario_id,
                "title": self.scenario_title,
                "total_parts": self.total_parts,
                "total_steps": self.total_steps,
            },
            "current": {
                "part": self.current_part,
                "step": self.current_step_index,
                "account": self.current_account,
            },
            "status": self.status,
            "created_at": self.created_at.isoformat(),
        }

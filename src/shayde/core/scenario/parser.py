"""YAML scenario parser."""

from __future__ import annotations

import os
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional, Union

import yaml

from shayde.core.scenario.models import Priority, CoverageStatus


@dataclass
class Account:
    """Account definition."""
    key: str
    email: str
    password: str
    role: Optional[str] = None


@dataclass
class Coverage:
    """Coverage item."""
    id: int
    name: str
    status: CoverageStatus


@dataclass
class Step:
    """Single test step."""
    id: str
    desc: str
    action: Optional[Union[dict, list[dict]]] = None
    expect: Optional[Union[dict, list[dict]]] = None
    screenshot: Union[bool, str] = False

    @property
    def has_screenshot(self) -> bool:
        """Check if screenshot is enabled."""
        return bool(self.screenshot)

    @property
    def screenshot_name(self) -> Optional[str]:
        """Get screenshot name if specified."""
        if isinstance(self.screenshot, str):
            return self.screenshot
        return None

    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            "id": self.id,
            "desc": self.desc,
            "action": self.action,
            "expect": self.expect,
            "screenshot": self.screenshot,
        }


@dataclass
class Part:
    """Test part (group of steps)."""
    part: int
    title: str
    account: Optional[str] = None
    items: list[Step] = field(default_factory=list)

    @property
    def step_count(self) -> int:
        return len(self.items)

    @property
    def screenshot_count(self) -> int:
        return sum(1 for s in self.items if s.has_screenshot)

    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            "part": self.part,
            "title": self.title,
            "account": self.account,
            "items": [s.to_dict() for s in self.items],
        }


@dataclass
class Meta:
    """Scenario metadata."""
    id: str
    title: str
    priority: Priority = Priority.MEDIUM
    estimated_time: Optional[int] = None
    depends_on: list[str] = field(default_factory=list)


@dataclass
class Scenario:
    """Parsed scenario."""
    version: int
    meta: Meta
    prerequisites: list[str] = field(default_factory=list)
    coverage: list[Coverage] = field(default_factory=list)
    accounts: dict[str, Account] = field(default_factory=dict)
    steps: list[Part] = field(default_factory=list)
    pass_criteria: list[str] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)
    test_files: list[dict] = field(default_factory=list)
    source_path: Optional[Path] = None

    @property
    def total_steps(self) -> int:
        return sum(p.step_count for p in self.steps)

    @property
    def total_screenshots(self) -> int:
        return sum(p.screenshot_count for p in self.steps)

    def get_step(self, step_id: str) -> Optional[Step]:
        """Get step by ID."""
        for part in self.steps:
            for step in part.items:
                if step.id == step_id:
                    return step
        return None

    def get_part_for_step(self, step_id: str) -> Optional[Part]:
        """Get part containing the step."""
        for part in self.steps:
            for step in part.items:
                if step.id == step_id:
                    return part
        return None

    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            "version": self.version,
            "meta": {
                "id": self.meta.id,
                "title": self.meta.title,
                "priority": self.meta.priority.value,
                "estimated_time": self.meta.estimated_time,
                "depends_on": self.meta.depends_on,
            },
            "prerequisites": self.prerequisites,
            "coverage": [
                {"id": c.id, "name": c.name, "status": c.status.value}
                for c in self.coverage
            ],
            "accounts": {
                k: {"email": v.email, "role": v.role}
                for k, v in self.accounts.items()
            },
            "steps": [p.to_dict() for p in self.steps],
            "pass_criteria": self.pass_criteria,
            "notes": self.notes,
            "summary": {
                "total_parts": len(self.steps),
                "total_steps": self.total_steps,
                "total_screenshots": self.total_screenshots,
            },
        }


def expand_env_vars(data: Any) -> Any:
    """Recursively expand ${VAR} patterns in data with environment variables.

    Args:
        data: Data structure (dict, list, or str)

    Returns:
        Data with environment variables expanded
    """
    if isinstance(data, str):
        # Replace ${VAR} with os.environ.get('VAR', '')
        pattern = re.compile(r'\$\{([^}]+)\}')
        def replacer(match):
            var_name = match.group(1)
            return os.environ.get(var_name, '')
        return pattern.sub(replacer, data)
    elif isinstance(data, dict):
        return {k: expand_env_vars(v) for k, v in data.items()}
    elif isinstance(data, list):
        return [expand_env_vars(item) for item in data]
    else:
        return data


class ScenarioParser:
    """YAML scenario parser."""

    def __init__(self):
        self.errors: list[str] = []
        self.warnings: list[str] = []

    def parse(self, path: Path) -> Scenario:
        """Parse scenario from YAML file.

        Args:
            path: Path to YAML file

        Returns:
            Parsed Scenario object

        Raises:
            ValueError: If parsing fails
        """
        self.errors = []
        self.warnings = []

        if not path.exists():
            raise ValueError(f"Scenario file not found: {path}")

        with open(path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f)

        if not data:
            raise ValueError(f"Empty scenario file: {path}")

        # Expand environment variables in the data
        data = expand_env_vars(data)

        return self._parse_scenario(data, path)

    def parse_string(self, content: str) -> Scenario:
        """Parse scenario from YAML string.

        Args:
            content: YAML content

        Returns:
            Parsed Scenario object
        """
        self.errors = []
        self.warnings = []

        data = yaml.safe_load(content)
        if not data:
            raise ValueError("Empty scenario content")

        return self._parse_scenario(data, None)

    def _parse_scenario(self, data: dict, source_path: Optional[Path]) -> Scenario:
        """Parse scenario from dictionary."""
        # Version
        version = data.get("version", 1)

        # Meta
        meta_data = data.get("meta", {})
        meta = Meta(
            id=meta_data.get("id", "unknown"),
            title=meta_data.get("title", "Untitled"),
            priority=Priority(meta_data.get("priority", "medium")),
            estimated_time=meta_data.get("estimated_time"),
            depends_on=meta_data.get("depends_on", []),
        )

        # Prerequisites
        prerequisites = data.get("prerequisites", [])

        # Coverage
        coverage = []
        for c in data.get("coverage", []):
            coverage.append(Coverage(
                id=c.get("id", 0),
                name=c.get("name", ""),
                status=CoverageStatus(c.get("status", "complete")),
            ))

        # Accounts
        accounts = {}
        for key, acc in data.get("accounts", {}).items():
            accounts[key] = Account(
                key=key,
                email=acc.get("email", ""),
                password=acc.get("password", ""),
                role=acc.get("role"),
            )

        # Steps (Parts)
        steps = []
        for part_data in data.get("steps", []):
            part = self._parse_part(part_data)
            steps.append(part)

        # Pass criteria
        pass_criteria = data.get("pass_criteria", [])

        # Notes
        notes = data.get("notes", [])

        # Test files
        test_files = data.get("test_files", [])

        return Scenario(
            version=version,
            meta=meta,
            prerequisites=prerequisites,
            coverage=coverage,
            accounts=accounts,
            steps=steps,
            pass_criteria=pass_criteria,
            notes=notes,
            test_files=test_files,
            source_path=source_path,
        )

    def _parse_part(self, data: dict) -> Part:
        """Parse a part from dictionary."""
        items = []
        for item_data in data.get("items", []):
            step = self._parse_step(item_data)
            items.append(step)

        return Part(
            part=data.get("part", 0),
            title=data.get("title", ""),
            account=data.get("account"),
            items=items,
        )

    def _parse_step(self, data: dict) -> Step:
        """Parse a step from dictionary."""
        return Step(
            id=str(data.get("id", "")),
            desc=data.get("desc", ""),
            action=data.get("action"),
            expect=data.get("expect"),
            screenshot=data.get("screenshot", False),
        )

    def validate(self, scenario: Scenario) -> tuple[bool, list[str], list[str]]:
        """Validate a parsed scenario.

        Args:
            scenario: Parsed scenario

        Returns:
            Tuple of (is_valid, errors, warnings)
        """
        errors = []
        warnings = []

        # Check meta
        if not scenario.meta.id:
            errors.append("Missing meta.id")
        if not scenario.meta.title:
            warnings.append("Missing meta.title")

        # Check steps
        if not scenario.steps:
            errors.append("No steps defined")

        # Check step IDs are unique
        step_ids = set()
        for part in scenario.steps:
            for step in part.items:
                if step.id in step_ids:
                    errors.append(f"Duplicate step ID: {step.id}")
                step_ids.add(step.id)

        # Check account references
        for part in scenario.steps:
            if part.account and part.account not in scenario.accounts:
                warnings.append(
                    f"Part {part.part} references undefined account: {part.account}"
                )

            for step in part.items:
                # Check login action references
                if step.action and isinstance(step.action, dict):
                    login_account = step.action.get("login")
                    if login_account and login_account not in scenario.accounts:
                        warnings.append(
                            f"Step {step.id} references undefined account: {login_account}"
                        )

        is_valid = len(errors) == 0
        return is_valid, errors, warnings


def sanitize_filename(text: str, max_length: int = 50) -> str:
    """Sanitize text for use in filename.

    Args:
        text: Text to sanitize
        max_length: Maximum length

    Returns:
        Sanitized filename-safe string
    """
    # Replace problematic characters
    sanitized = re.sub(r'[<>:"/\\|?*]', "_", text)
    # Replace multiple underscores/spaces with single underscore
    sanitized = re.sub(r"[\s_]+", "_", sanitized)
    # Remove leading/trailing underscores
    sanitized = sanitized.strip("_")
    # Truncate
    if len(sanitized) > max_length:
        sanitized = sanitized[:max_length].rstrip("_")
    return sanitized

# Step-by-Step Scenario Execution API Design

## Overview

シナリオをステップ単位で対話的に実行するためのAPIを追加。
外部ツール（Claude Code等）がステップ実行を制御し、各ステップの結果を確認しながら進行できるようにする。

## Current Architecture

```
現状:
┌─────────────────────────────────────────┐
│ shayde scenario run scenario.yaml       │
│   └─► ScenarioRunner.run_all()          │
│        └─► 全パート・全ステップを一括実行│
└─────────────────────────────────────────┘
```

## Proposed Architecture

```
新規:
┌─────────────────────────────────────────────────────────────┐
│ shayde scenario session start scenario.yaml                  │
│   └─► SessionManager.create()                               │
│        └─► session_id を返却                                │
│                                                              │
│ shayde scenario session step <session_id>                   │
│   └─► SessionManager.execute_next_step()                    │
│        └─► StepResult (JSON) を返却                         │
│                                                              │
│ shayde scenario session end <session_id>                    │
│   └─► SessionManager.cleanup()                              │
│        └─► 最終レポート・ビデオを返却                       │
└─────────────────────────────────────────────────────────────┘
```

## New Commands

### `shayde scenario session start`

セッションを開始し、ブラウザを初期化。

```bash
shayde scenario session start <yaml_path> [OPTIONS]

Options:
  --output-dir PATH    Output directory for screenshots/video
  --base-url TEXT      Base URL override
  --video/--no-video   Record video (default: true)
  --part INT           Start from specific part
  --json               Output as JSON

Output (JSON):
{
  "session_id": "abc123",
  "scenario": {
    "id": "03-messaging-basic",
    "title": "メッセージング基本フロー",
    "total_parts": 7,
    "total_steps": 23
  },
  "current": {
    "part": 1,
    "step": 0,
    "account": null
  },
  "status": "initialized"
}
```

### `shayde scenario session step`

次のステップを実行。

```bash
shayde scenario session step <session_id> [OPTIONS]

Options:
  --retry              Retry current step
  --skip               Skip current step
  --json               Output as JSON

Output (JSON):
{
  "session_id": "abc123",
  "step": {
    "id": "1-1",
    "desc": "チャット画面に遷移",
    "part": 1,
    "part_title": "ダイレクトメッセージ開始"
  },
  "result": {
    "status": "passed",  # passed | failed | skipped
    "duration_ms": 1234,
    "screenshot": "screenshots/part-01_step-1-1_chat_list.png",
    "assertions": [
      {"type": "url_contains", "expected": "/chat", "passed": true}
    ],
    "error": null
  },
  "next": {
    "part": 1,
    "step": "1-2",
    "is_part_change": false,
    "is_account_change": false,
    "is_completed": false
  }
}
```

### `shayde scenario session end`

セッションを終了し、リソースを解放。

```bash
shayde scenario session end <session_id> [OPTIONS]

Options:
  --json               Output as JSON

Output (JSON):
{
  "session_id": "abc123",
  "result": {
    "status": "passed",  # passed | failed | partial
    "total_steps": 23,
    "passed": 20,
    "failed": 2,
    "skipped": 1,
    "duration_ms": 45678
  },
  "output": {
    "results_json": "screenshots/03-messaging-basic_.../results.json",
    "video": "screenshots/03-messaging-basic_....webm"
  }
}
```

### `shayde scenario session list`

アクティブなセッション一覧。

```bash
shayde scenario session list [--json]

Output:
SESSION_ID  SCENARIO             PART  STEP   STATUS    CREATED
abc123      03-messaging-basic   1     1-2    active    2025-01-01 12:00:00
def456      01-authentication    3     3-1    paused    2025-01-01 11:30:00
```

### `shayde scenario session info`

セッション詳細情報。

```bash
shayde scenario session info <session_id> [--json]
```

## Implementation Plan

### Phase 2-1: SessionManager Class

```python
# src/shayde/core/scenario/session_manager.py

from dataclasses import dataclass
from typing import Optional, Dict
from pathlib import Path
import uuid
import asyncio

@dataclass
class ManagedSession:
    id: str
    scenario: Scenario
    session: ScenarioSession
    runner: ScenarioRunner
    current_part_index: int
    current_step_index: int
    status: str  # initialized, running, paused, completed, error
    created_at: datetime

class SessionManager:
    """ステップ単位実行のためのセッション管理"""

    _sessions: Dict[str, ManagedSession] = {}

    @classmethod
    async def create(
        cls,
        yaml_path: Path,
        output_dir: Optional[Path] = None,
        base_url: Optional[str] = None,
        record_video: bool = True,
        start_part: int = 1,
    ) -> ManagedSession:
        """新規セッションを作成"""
        session_id = str(uuid.uuid4())[:8]

        # シナリオ読み込み
        scenario = parse_scenario(yaml_path)

        # ブラウザ接続
        browser_manager = BrowserManager(config)
        await browser_manager.connect()
        browser = browser_manager.browser

        # セッション初期化
        scenario_session = ScenarioSession(
            scenario=scenario,
            output_dir=output_dir or Path(f"screenshots/{scenario.meta.id}"),
            browser=browser,
            base_url=base_url,
            record_video=record_video,
        )
        await scenario_session.setup()

        # ランナー初期化
        runner = ScenarioRunner(scenario_session)

        managed = ManagedSession(
            id=session_id,
            scenario=scenario,
            session=scenario_session,
            runner=runner,
            current_part_index=start_part - 1,
            current_step_index=0,
            status="initialized",
            created_at=datetime.now(),
        )

        cls._sessions[session_id] = managed
        return managed

    @classmethod
    async def execute_next_step(
        cls,
        session_id: str,
        retry: bool = False,
        skip: bool = False,
    ) -> StepExecutionResult:
        """次のステップを実行"""
        managed = cls._sessions.get(session_id)
        if not managed:
            raise ValueError(f"Session not found: {session_id}")

        # 現在のパート・ステップを取得
        part = managed.scenario.steps[managed.current_part_index]
        step = part.items[managed.current_step_index]

        # アカウント切り替えが必要な場合
        if part.account != managed.session.current_account:
            await managed.session.switch_account(part.account)

        # ステップ実行
        if skip:
            result = StepResult(
                step_id=step.id,
                desc=step.desc,
                status=StepStatus.SKIPPED,
            )
        else:
            result = await managed.runner.run_step(step, part)

        # 次のステップへ進む
        is_completed = False
        is_part_change = False
        is_account_change = False

        if not retry:
            managed.current_step_index += 1

            # パート内の全ステップ完了
            if managed.current_step_index >= len(part.items):
                managed.current_step_index = 0
                managed.current_part_index += 1
                is_part_change = True

                # 全パート完了
                if managed.current_part_index >= len(managed.scenario.steps):
                    is_completed = True
                    managed.status = "completed"
                else:
                    next_part = managed.scenario.steps[managed.current_part_index]
                    if next_part.account != part.account:
                        is_account_change = True

        return StepExecutionResult(
            session_id=session_id,
            step=step,
            result=result,
            is_completed=is_completed,
            is_part_change=is_part_change,
            is_account_change=is_account_change,
            next_part=managed.current_part_index + 1,
            next_step=managed.scenario.steps[managed.current_part_index].items[managed.current_step_index].id if not is_completed else None,
        )

    @classmethod
    async def end(cls, session_id: str) -> SessionEndResult:
        """セッションを終了"""
        managed = cls._sessions.pop(session_id, None)
        if not managed:
            raise ValueError(f"Session not found: {session_id}")

        # 結果保存
        managed.session.finish_scenario()
        results_path = managed.session.save_results()

        # ビデオ保存
        video_path = None
        if managed.session.record_video:
            video_path = await managed.session.save_video()

        # クリーンアップ
        await managed.session.teardown()

        return SessionEndResult(
            session_id=session_id,
            status=managed.status,
            results_path=results_path,
            video_path=video_path,
        )

    @classmethod
    def list_sessions(cls) -> list[ManagedSession]:
        """アクティブセッション一覧"""
        return list(cls._sessions.values())

    @classmethod
    def get_session(cls, session_id: str) -> Optional[ManagedSession]:
        """セッション取得"""
        return cls._sessions.get(session_id)
```

### Phase 2-2: CLI Commands

```python
# src/shayde/cli/scenario.py に追加

@scenario.group("session")
def session_group():
    """Step-by-step scenario execution"""
    pass

@session_group.command("start")
def session_start(
    yaml_path: Path,
    output_dir: Optional[Path] = None,
    base_url: Optional[str] = None,
    video: bool = True,
    part: int = 1,
    json_output: bool = typer.Option(False, "--json"),
):
    """Start a new scenario session"""
    async def _start():
        managed = await SessionManager.create(
            yaml_path=yaml_path,
            output_dir=output_dir,
            base_url=base_url,
            record_video=video,
            start_part=part,
        )
        return managed

    managed = asyncio.run(_start())

    if json_output:
        print(json.dumps({
            "session_id": managed.id,
            "scenario": {
                "id": managed.scenario.meta.id,
                "title": managed.scenario.meta.title,
                "total_parts": len(managed.scenario.steps),
                "total_steps": sum(len(p.items) for p in managed.scenario.steps),
            },
            "status": managed.status,
        }))
    else:
        console.print(f"Session started: [bold green]{managed.id}[/]")

@session_group.command("step")
def session_step(
    session_id: str,
    retry: bool = False,
    skip: bool = False,
    json_output: bool = typer.Option(False, "--json"),
):
    """Execute next step in session"""
    async def _step():
        return await SessionManager.execute_next_step(
            session_id=session_id,
            retry=retry,
            skip=skip,
        )

    result = asyncio.run(_step())

    if json_output:
        print(json.dumps(result.to_dict()))
    else:
        status_icon = "✅" if result.result.status == StepStatus.PASSED else "❌"
        console.print(f"{status_icon} Step {result.step.id}: {result.step.desc}")

@session_group.command("end")
def session_end(
    session_id: str,
    json_output: bool = typer.Option(False, "--json"),
):
    """End a scenario session"""
    async def _end():
        return await SessionManager.end(session_id)

    result = asyncio.run(_end())

    if json_output:
        print(json.dumps(result.to_dict()))
    else:
        console.print(f"Session ended: {session_id}")
        console.print(f"Results: {result.results_path}")

@session_group.command("list")
def session_list(json_output: bool = typer.Option(False, "--json")):
    """List active sessions"""
    sessions = SessionManager.list_sessions()

    if json_output:
        print(json.dumps([s.to_dict() for s in sessions]))
    else:
        table = Table()
        table.add_column("ID")
        table.add_column("Scenario")
        table.add_column("Part")
        table.add_column("Status")

        for s in sessions:
            table.add_row(s.id, s.scenario.meta.id, str(s.current_part_index + 1), s.status)

        console.print(table)
```

### Phase 2-3: Data Models

```python
# src/shayde/core/scenario/models.py に追加

@dataclass
class StepExecutionResult:
    session_id: str
    step: Step
    result: StepResult
    is_completed: bool
    is_part_change: bool
    is_account_change: bool
    next_part: Optional[int]
    next_step: Optional[str]

    def to_dict(self) -> dict:
        return {
            "session_id": self.session_id,
            "step": {
                "id": self.step.id,
                "desc": self.step.desc,
            },
            "result": {
                "status": self.result.status.value,
                "duration_ms": self.result.duration_ms,
                "screenshot": str(self.result.screenshot) if self.result.screenshot else None,
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
    session_id: str
    status: str
    results_path: Path
    video_path: Optional[Path]

    def to_dict(self) -> dict:
        return {
            "session_id": self.session_id,
            "status": self.status,
            "output": {
                "results_json": str(self.results_path),
                "video": str(self.video_path) if self.video_path else None,
            },
        }
```

## File Changes Summary

| File | Action | Description |
|------|--------|-------------|
| `src/shayde/core/scenario/session_manager.py` | New | セッション管理クラス |
| `src/shayde/core/scenario/models.py` | Edit | 新データクラス追加 |
| `src/shayde/cli/scenario.py` | Edit | session サブコマンド追加 |
| `docs/commands/scenario.md` | Edit | 新コマンドのドキュメント |
| `README.md` | Edit | 機能概要更新 |

## Usage Example

```bash
# セッション開始
$ shayde scenario session start tests/03-messaging-basic.yaml --json
{"session_id": "abc123", "status": "initialized", ...}

# ステップ実行（繰り返し）
$ shayde scenario session step abc123 --json
{"step": {"id": "1-1"}, "result": {"status": "passed"}, ...}

$ shayde scenario session step abc123 --json
{"step": {"id": "1-2"}, "result": {"status": "failed"}, ...}

# 失敗時: リトライ or スキップ
$ shayde scenario session step abc123 --retry --json
$ shayde scenario session step abc123 --skip --json

# セッション終了
$ shayde scenario session end abc123 --json
{"results_json": "...", "video": "..."}
```

## Integration with Claude Code

```markdown
# e2e-interactive スキル (Phase 2対応版)

## Instructions

### Part単位 → ステップ単位に変更

1. セッション開始
   ```bash
   result=$(shayde scenario session start {yaml} --json)
   session_id=$(echo $result | jq -r '.session_id')
   ```

2. ステップ実行ループ
   ```bash
   while true; do
     result=$(shayde scenario session step $session_id --json)

     # スクリーンショット確認
     screenshot=$(echo $result | jq -r '.result.screenshot')
     Read: $screenshot

     # 失敗時
     if [ $(echo $result | jq -r '.result.status') == "failed" ]; then
       AskUserQuestion: リトライ / スキップ / 中止
     fi

     # 完了チェック
     if [ $(echo $result | jq -r '.next.is_completed') == "true" ]; then
       break
     fi
   done
   ```

3. セッション終了
   ```bash
   shayde scenario session end $session_id --json
   ```
```

## Notes

- セッションはプロセス内メモリで管理（永続化なし）
- 同時実行可能なセッション数は制限なし
- タイムアウトによる自動クリーンアップは未実装（将来対応）

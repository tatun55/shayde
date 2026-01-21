# Scenario Session Commands

ステップバイステップでシナリオを実行するためのコマンド群。
外部ツール（Claude Code等）との連携や、対話的なデバッグに最適。

## 概要

```
shayde scenario session <subcommand>

Subcommands:
  start   新規セッション開始
  step    次のステップ実行
  end     セッション終了
  list    アクティブセッション一覧
  info    セッション詳細表示
```

## コマンド詳細

### `shayde scenario session start`

新規セッションを開始し、ブラウザを初期化。

```bash
shayde scenario session start <yaml_path> [OPTIONS]

Arguments:
  yaml_path           シナリオYAMLファイルのパス

Options:
  -o, --output PATH   スクリーンショット出力先
  -b, --base-url URL  ベースURL上書き
  --video/--no-video  ビデオ録画（デフォルト: on）
  -p, --part INT      開始Part番号（デフォルト: 1）
  -j, --json          JSON出力
```

**例:**

```bash
# 基本
$ shayde scenario session start tests/03-messaging.yaml
Session started: a1b2c3d4
  Scenario: メッセージング基本フロー
  Parts: 7
  Steps: 23

Run steps with: shayde scenario session step a1b2c3d4

# Part 3 から開始
$ shayde scenario session start tests/03-messaging.yaml --part 3

# JSON 出力（外部ツール連携用）
$ shayde scenario session start tests/03-messaging.yaml --json
```

**JSON 出力:**

```json
{
  "session_id": "a1b2c3d4",
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
  "status": "initialized",
  "created_at": "2025-01-01T12:00:00"
}
```

---

### `shayde scenario session step`

次のステップを実行。

```bash
shayde scenario session step <session_id> [OPTIONS]

Arguments:
  session_id          セッションID

Options:
  -r, --retry         現在のステップをリトライ
  -s, --skip          現在のステップをスキップ
  -j, --json          JSON出力
```

**例:**

```bash
# 次のステップを実行
$ shayde scenario session step a1b2c3d4
✓ Step 1-1: チャット画面に遷移
  Part: 1 - ダイレクトメッセージ開始
  Duration: 1234ms
  📸 screenshots/part-01_step-1-1_chat_list.png

  Next: Part 1, Step 1-2

# 失敗したステップをリトライ
$ shayde scenario session step a1b2c3d4 --retry

# ステップをスキップ
$ shayde scenario session step a1b2c3d4 --skip
```

**JSON 出力:**

```json
{
  "session_id": "a1b2c3d4",
  "step": {
    "id": "1-1",
    "desc": "チャット画面に遷移",
    "part": 1,
    "part_title": "ダイレクトメッセージ開始"
  },
  "result": {
    "status": "passed",
    "duration_ms": 1234,
    "screenshot": "screenshots/.../part-01_step-1-1_chat_list.png",
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

---

### `shayde scenario session end`

セッションを終了し、リソースを解放。

```bash
shayde scenario session end <session_id> [OPTIONS]

Arguments:
  session_id          セッションID

Options:
  -j, --json          JSON出力
```

**例:**

```bash
$ shayde scenario session end a1b2c3d4
Session ended: PASSED
  Total: 23 steps
  Passed: 21
  Failed: 1
  Skipped: 1
  Duration: 45.6s
  Results: screenshots/03-messaging-basic_.../results.json
  🎬 Video: screenshots/03-messaging-basic_....webm
```

**JSON 出力:**

```json
{
  "session_id": "a1b2c3d4",
  "result": {
    "status": "passed",
    "total_steps": 23,
    "passed": 21,
    "failed": 1,
    "skipped": 1,
    "duration_ms": 45678
  },
  "output": {
    "results_json": "screenshots/.../results.json",
    "video": "screenshots/....webm"
  }
}
```

---

### `shayde scenario session list`

アクティブなセッション一覧を表示。

```bash
shayde scenario session list [OPTIONS]

Options:
  -j, --json          JSON出力
```

**例:**

```bash
$ shayde scenario session list
               Active Sessions
┏━━━━━━━━━━━━━┳━━━━━━━━━━━━━━━━━━━━━━┳━━━━━━┳━━━━━━┳━━━━━━━━━━━━┳━━━━━━━━━━┓
┃ Session ID  ┃ Scenario             ┃ Part ┃ Step ┃ Status     ┃ Created  ┃
┡━━━━━━━━━━━━━╇━━━━━━━━━━━━━━━━━━━━━━╇━━━━━━╇━━━━━━╇━━━━━━━━━━━━╇━━━━━━━━━━┩
│ a1b2c3d4    │ 03-messaging-basic   │ 2    │ 3    │ paused     │ 12:00:00 │
│ e5f6g7h8    │ 01-authentication    │ 1    │ 1    │ initialized│ 11:45:00 │
└─────────────┴──────────────────────┴──────┴──────┴────────────┴──────────┘
```

---

### `shayde scenario session info`

セッションの詳細情報を表示。

```bash
shayde scenario session info <session_id> [OPTIONS]

Arguments:
  session_id          セッションID

Options:
  -j, --json          JSON出力
```

**例:**

```bash
$ shayde scenario session info a1b2c3d4
Session a1b2c3d4
  Scenario: メッセージング基本フロー (03-messaging-basic)
  Status: paused
  Current: Part 2, Step 3
  Account: user_a
  Progress: 8/23 steps
  Created: 2025-01-01 12:00:00
```

---

## 使用例: 対話的テスト

```bash
# 1. セッション開始
$ session_id=$(shayde scenario session start tests/03-messaging.yaml --json | jq -r '.session_id')

# 2. ステップを実行（ループ）
while true; do
  result=$(shayde scenario session step $session_id --json)

  # 結果を確認
  status=$(echo $result | jq -r '.result.status')
  if [ "$status" == "failed" ]; then
    echo "Step failed! Retry or skip?"
    read choice
    if [ "$choice" == "retry" ]; then
      shayde scenario session step $session_id --retry --json
    else
      shayde scenario session step $session_id --skip --json
    fi
  fi

  # 完了チェック
  completed=$(echo $result | jq -r '.next.is_completed')
  if [ "$completed" == "true" ]; then
    break
  fi
done

# 3. セッション終了
shayde scenario session end $session_id --json
```

---

## Claude Code 連携

`/e2e-interactive` スキルと連携:

```markdown
## Instructions

1. セッション開始
   result = Bash: shayde scenario session start {yaml} --json
   session_id = JSONから抽出

2. ステップ実行ループ
   - result = Bash: shayde scenario session step {session_id} --json
   - screenshot を Read tool で確認
   - 失敗時は AskUserQuestion で対応選択
   - 完了まで繰り返し

3. セッション終了
   Bash: shayde scenario session end {session_id} --json
```

---

## ステータス

| Status | 説明 |
|--------|------|
| `initialized` | セッション作成直後 |
| `running` | ステップ実行中 |
| `paused` | ステップ完了、次を待機 |
| `completed` | 全ステップ完了 |
| `error` | エラー発生 |

---

## 注意事項

- セッションはプロセスメモリで管理（永続化なし）
- プロセス終了時にセッションは失われる
- 同時に複数セッションを実行可能
- タイムアウトによる自動クリーンアップは未実装

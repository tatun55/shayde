# Shayde

Docker Playwright を使用した E2E テスト・スクリーンショットキャプチャツール。
Host Proxy 方式により、各プロジェクトの Vite 設定変更なしで動作。

## 特徴

- **Host Proxy**: Vite 開発サーバーへの透過的なプロキシ（設定変更不要）
- **日本語フォント対応**: Mac/Windows スタイルのフォント切り替え
- **認証サポート**: ログイン後のページもキャプチャ可能
- **レスポンシブ対応**: mobile/tablet/desktop の一括キャプチャ

## インストール

```bash
# GitHubからインストール
pip install git+https://github.com/tatun55/shayde.git

# または、ローカルでクローンしてインストール
git clone https://github.com/tatun55/shayde.git
cd shayde
pip install -e .
```

## クイックスタート

```bash
# Docker イメージをビルド（日本語フォント込み）
shayde docker build

# コンテナ起動
shayde docker start

# スクリーンショット撮影
shayde capture page /login

# 認証付きキャプチャ
shayde capture auth /dashboard /profile -e user@example.com -p password

# Mac/Windows フォントで比較キャプチャ
shayde capture platforms /login
```

## コマンド一覧

### グローバルオプション

```bash
shayde --version          # バージョン表示
shayde --config FILE      # 設定ファイルを指定
shayde --verbose          # 詳細ログ出力
```

### キャプチャ

```bash
# 単一ページ
shayde capture page /login
shayde capture page /login --platform mac      # Macフォント
shayde capture page /login --platform windows  # Windowsフォント
shayde capture page /login --viewport mobile   # モバイルサイズ
shayde capture page /login --width 1440 --height 900  # カスタムサイズ
shayde capture page /login --full-page         # フルページ

# 複数ページ（並列）
shayde capture batch /page1 /page2 /page3 --parallel 3

# レスポンシブ（全ビューポート）
shayde capture responsive /login

# プラットフォーム別フォント（Mac + Windows 同時）
shayde capture platforms /login

# 認証付き
shayde capture auth /dashboard /profile -e email -p password
shayde capture auth /dashboard --login-url /admin/login -e admin@example.com -p password
```

### Docker 管理

```bash
shayde docker start    # コンテナ起動
shayde docker stop     # コンテナ停止
shayde docker restart  # コンテナ再起動
shayde docker status   # 状態確認
shayde docker build    # カスタムイメージビルド（フォント込み）
shayde docker build -f # 強制再ビルド
shayde docker logs     # ログ表示
shayde docker logs -f  # ログをフォロー
```

### E2E テスト

```bash
shayde test init                      # テスト環境セットアップ
shayde test run                       # テスト実行
shayde test run --headed              # ブラウザ表示モードで実行
shayde test run --debug               # デバッグモードで実行
shayde test run tests/e2e/login.ts    # 特定ファイルのみ実行
shayde test run --grep "ログイン"      # 特定テストのみ実行
shayde test run --workers 4           # 並列実行
shayde test run --update-snapshots    # スナップショット更新
shayde test run --skip-before         # before コマンドをスキップ
shayde test list                      # テストファイル一覧
```

### シナリオテスト

```bash
# 一括実行
shayde scenario run scenario.yaml                  # 全ステップ実行
shayde scenario run scenario.yaml --part 2         # Part 2 のみ
shayde scenario run scenario.yaml -e               # エラー時停止

# ステップバイステップ実行（対話的）
shayde scenario session start scenario.yaml        # セッション開始
shayde scenario session step <session_id>          # 次のステップ実行
shayde scenario session step <session_id> --retry  # リトライ
shayde scenario session step <session_id> --skip   # スキップ
shayde scenario session end <session_id>           # セッション終了
shayde scenario session list                       # アクティブセッション一覧
shayde scenario session info <session_id>          # セッション詳細

# シナリオ解析
shayde scenario parse scenario.yaml                # 構造表示
shayde scenario list scenario.yaml                 # ステップ一覧
```

### 設定管理

```bash
shayde config show      # 現在の設定を表示
shayde config init      # .shayde.yaml を生成
shayde config validate  # 設定ファイルを検証
```

## 設定ファイル (.shayde.yaml)

プロジェクトルートに配置すると自動読み込み。

```yaml
version: 1

app:
  base_url: null            # 自動検出（.env の APP_URL）
  env_file: .env
  env_var: APP_URL

proxy:
  enabled: true
  port: 9999
  vite_port: null           # 自動検出

docker:
  playwright_version: "1.48.0"
  container_name: "shayde-playwright"
  ws_port: 3000
  auto_start: true
  auto_stop: false
  use_custom_image: true    # フォント入りイメージを使用
  image_name: "shayde-playwright"

fonts:
  platform: neutral         # neutral, mac, windows
  custom_fonts_dir: null    # カスタムフォントディレクトリ

output:
  directory: "storage/screenshots"
  filename_pattern: "{name}_{date}_{time}.png"
  date_format: "%Y-%m-%d"
  time_format: "%H%M%S"

viewports:
  mobile:
    width: 375
    height: 812
    device_scale_factor: 2
  tablet:
    width: 768
    height: 1024
  desktop:
    width: 1920
    height: 1080

capture:
  default_viewport: desktop
  wait_until: networkidle   # load, domcontentloaded, networkidle
  wait_after: 0             # 追加待機時間(ms)
  full_page: false

test:
  directory: "tests/e2e"
  before: "php artisan migrate:fresh --seed"  # テスト前に実行
  timeout: 30000            # テストタイムアウト(ms)
  workers: 1                # 並列ワーカー数
  retries: 0                # リトライ回数
```

## アーキテクチャ

```
┌─────────────────────────────────────────────────────────────┐
│                      Host Machine                            │
│  ┌─────────────┐    ┌─────────────┐    ┌─────────────┐      │
│  │   Valet     │    │    Vite     │    │   Shayde    │      │
│  │ (PHP App)   │    │ (localhost  │    │   Proxy     │      │
│  │ :80/:443    │    │  :5173)     │    │ (0.0.0.0    │      │
│  └──────┬──────┘    └──────┬──────┘    │  :9999)     │      │
│         │                  │           └──────┬──────┘      │
│         └──────────────────┼──────────────────┤             │
│                            ▼                  ▼             │
│  ┌──────────────────────────────────────────────────────┐   │
│  │              host-gateway (Docker bridge)             │   │
│  └──────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│                    Docker Container                          │
│  ┌─────────────────────────────────────────────────────┐    │
│  │                 Playwright Browser                   │    │
│  │   - Noto Sans CJK JP (neutral/windows)              │    │
│  │   - Source Han Sans JP (mac)                        │    │
│  └─────────────────────────────────────────────────────┘    │
└─────────────────────────────────────────────────────────────┘
```

## 日本語フォント

| プラットフォーム | フォント | 説明 |
|-----------------|---------|------|
| `neutral` | Noto Sans CJK JP | デフォルト、クロスプラットフォーム |
| `mac` | Source Han Sans JP | ヒラギノ角ゴシック風（Adobe製） |
| `windows` | Noto Sans CJK JP | メイリオ風（CSS で font-family 変更） |

カスタムイメージ (`shayde docker build`) には以下がプリインストール:
- **Noto Sans CJK JP** - 全ウェイト（Google製、オープンソース）
- **Source Han Sans JP** - 全ウェイト（Adobe製、オープンソース）

## 動作の仕組み

1. **Host Proxy**: Shayde は Vite 開発サーバー（localhost:5173）へのプロキシを 0.0.0.0:9999 で起動
2. **Route Interception**: Playwright のルートインターセプションで localhost/0.0.0.0 へのリクエストを host.docker.internal にリダイレクト
3. **CSS Injection**: `--platform` 指定時、ページ読み込み後にフォントファミリーを上書きする CSS を注入

## 要件

- Python 3.8+
- Docker Desktop（macOS/Windows）または Docker Engine（Linux）
- Laravel Valet（推奨、他の開発サーバーでも動作可能）

### サーバー環境

EC2 などのサーバー環境での常時起動設定は [Amazon Linux 2023 セットアップガイド](docs/setup-amazon-linux-2023.md) を参照。

## トラブルシューティング

### コンテナが起動しない

```bash
# 既存コンテナを削除して再起動
docker rm -f shayde-playwright
shayde docker start
```

### フォントが適用されない

```bash
# カスタムイメージを再ビルド
shayde docker build --force
shayde docker restart
```

### Vite の CSS/JS が読み込まれない

```bash
# Vite 開発サーバーが起動しているか確認
npm run dev

# プロキシが正しいポートを使用しているか確認
shayde config show
```

## ライセンス

MIT

# PlayCap

Docker Playwright を使用したスクリーンショット・キャプチャツール。
Host Proxy 方式により、各プロジェクトの Vite 設定変更なしで動作。

## 特徴

- **Host Proxy**: Vite 開発サーバーへの透過的なプロキシ（設定変更不要）
- **日本語フォント対応**: Mac/Windows スタイルのフォント切り替え
- **認証サポート**: ログイン後のページもキャプチャ可能
- **レスポンシブ対応**: mobile/tablet/desktop の一括キャプチャ

## インストール

```bash
pip install playcap
```

## クイックスタート

```bash
# Docker イメージをビルド（日本語フォント込み）
playcap docker build

# スクリーンショット撮影
playcap capture page /login

# 認証付きキャプチャ
playcap capture auth /dashboard /profile -e user@example.com -p password

# Mac/Windows フォントで比較キャプチャ
playcap capture platforms /login
```

## コマンド

### キャプチャ

```bash
# 単一ページ
playcap capture page /login

# 複数ページ（並列）
playcap capture batch /page1 /page2 /page3 --parallel 3

# レスポンシブ（全ビューポート）
playcap capture responsive /login

# プラットフォーム別フォント
playcap capture platforms /login  # Mac + Windows
playcap capture page /login --platform mac
playcap capture page /login --platform windows

# 認証付き
playcap capture auth /dashboard -e email -p password
```

### Docker 管理

```bash
playcap docker start   # コンテナ起動
playcap docker stop    # コンテナ停止
playcap docker status  # 状態確認
playcap docker build   # カスタムイメージビルド
playcap docker logs    # ログ表示
```

### 設定

```bash
playcap config show    # 現在の設定を表示
playcap config init    # .playcap.yaml を生成
```

## 設定ファイル (.playcap.yaml)

```yaml
version: 1

app:
  base_url: null            # 自動検出（.env の APP_URL）
  env_file: .env
  env_var: APP_URL

proxy:
  enabled: true
  port: 9999

docker:
  playwright_version: "1.48.0"
  container_name: "playcap-playwright"
  ws_port: 3000
  auto_start: true
  use_custom_image: true    # フォント入りイメージを使用

fonts:
  platform: neutral         # neutral, mac, windows

output:
  directory: "storage/screenshots"
  filename_pattern: "{name}_{date}_{time}.png"

viewports:
  mobile: { width: 375, height: 812, device_scale_factor: 2 }
  tablet: { width: 768, height: 1024 }
  desktop: { width: 1920, height: 1080 }
```

## アーキテクチャ

```
┌─────────────────────────────────────────────────────────────┐
│                      Host Machine                            │
│  ┌─────────────┐    ┌─────────────┐    ┌─────────────┐      │
│  │   Valet     │    │    Vite     │    │  PlayCap    │      │
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
│  │   - Noto Sans CJK (neutral)                         │    │
│  │   - Source Han Sans (Mac-style)                     │    │
│  └─────────────────────────────────────────────────────┘    │
└─────────────────────────────────────────────────────────────┘
```

## 日本語フォント

| プラットフォーム | フォント | 用途 |
|-----------------|---------|------|
| neutral | Noto Sans CJK JP | デフォルト |
| mac | Source Han Sans JP | Mac/Hiragino 風 |
| windows | Noto Sans CJK JP | Windows/メイリオ 風 |

カスタムイメージには以下のフォントがプリインストール:
- Noto Sans CJK JP（全ウェイト）
- Source Han Sans JP（Adobe、Mac風）

## 要件

- Python 3.8+
- Docker Desktop
- Laravel Valet（推奨）

## ライセンス

MIT

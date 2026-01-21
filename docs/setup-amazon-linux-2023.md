# Amazon Linux 2023 セットアップガイド

EC2（ARM64/Graviton）での Shayde 環境構築手順。

## 前提条件

```bash
# 確認
python3 --version  # 3.8+
docker --version   # 20.10+
git --version
```

## 1. Docker Compose プラグインのインストール

Amazon Linux 2023 には docker compose がデフォルトで含まれていない。

```bash
# インストール
sudo mkdir -p /usr/local/lib/docker/cli-plugins
sudo curl -SL "https://github.com/docker/compose/releases/download/v2.24.5/docker-compose-linux-$(uname -m)" \
  -o /usr/local/lib/docker/cli-plugins/docker-compose
sudo chmod +x /usr/local/lib/docker/cli-plugins/docker-compose

# 確認
docker compose version
```

## 2. Shayde インストール

```bash
cd /var/www
sudo mkdir -p shayde && sudo chown $USER:$USER shayde
git clone https://github.com/tatun55/shayde.git shayde
cd shayde

# 仮想環境
python3 -m venv venv
source venv/bin/activate
pip install -e .

# 確認
shayde --version
```

## 3. バージョン同期（重要）

**Playwright のバージョンは統一が必須。** pip でインストールされたバージョンと Docker イメージのバージョンを一致させる。

```bash
# インストール済みバージョン確認
pip show playwright | grep Version
# 例: Version: 1.57.0
```

### Dockerfile の更新

`docker/Dockerfile` のベースイメージを一致させる:

```dockerfile
# pip show playwright の結果に合わせる
FROM mcr.microsoft.com/playwright:v1.57.0-noble
```

### 設定ファイルの更新

`.shayde.yaml` も同様に:

```yaml
docker:
  playwright_version: "1.57.0"  # pip show playwright の結果に合わせる
```

## 4. 設定ファイル作成

```bash
cat > /var/www/shayde/.shayde.yaml << 'EOF'
version: 1

app:
  base_url: https://your-app.example.com

docker:
  playwright_version: "1.57.0"
  container_name: "shayde-playwright"
  ws_port: 3000
  auto_start: true
  auto_stop: false
  use_custom_image: true
  image_name: "shayde-playwright"

fonts:
  platform: neutral

output:
  directory: "storage/screenshots"

capture:
  default_viewport: desktop
  wait_until: networkidle
  wait_after: 1000
EOF
```

## 5. Docker イメージビルド & 起動

```bash
cd /var/www/shayde
source venv/bin/activate

# ビルド（5-10分）
shayde docker build

# 起動
shayde docker start

# 確認
shayde docker status
```

## 6. Systemd サービス（常時起動）

```bash
sudo tee /etc/systemd/system/shayde.service << 'EOF'
[Unit]
Description=Shayde Playwright Docker Container
After=docker.service
Requires=docker.service

[Service]
Type=oneshot
RemainAfterExit=yes
WorkingDirectory=/var/www/shayde
ExecStart=/var/www/shayde/venv/bin/shayde docker start
ExecStop=/var/www/shayde/venv/bin/shayde docker stop
Environment="PATH=/var/www/shayde/venv/bin:/usr/local/bin:/usr/bin:/bin"

[Install]
WantedBy=multi-user.target
EOF

sudo systemctl daemon-reload
sudo systemctl enable shayde
sudo systemctl start shayde
```

### 操作コマンド

```bash
sudo systemctl start shayde    # 起動
sudo systemctl stop shayde     # 停止
sudo systemctl restart shayde  # 再起動
sudo systemctl status shayde   # 状態確認
```

## 7. ヘルスチェック（オプション）

```bash
# スクリプト作成
cat > /var/www/shayde/healthcheck.sh << 'EOF'
#!/bin/bash
if docker ps --format '{{.Names}}' | grep -q "^shayde-playwright$"; then
    echo "OK: Container running"
    exit 0
else
    echo "ERROR: Container not running, restarting..."
    /var/www/shayde/venv/bin/shayde docker start
    exit 1
fi
EOF
chmod +x /var/www/shayde/healthcheck.sh

# cron インストール（Amazon Linux 2023）
sudo dnf install -y cronie
sudo systemctl enable crond --now

# 5分ごとにヘルスチェック
(crontab -l 2>/dev/null; echo "*/5 * * * * /var/www/shayde/healthcheck.sh >> /var/log/shayde-health.log 2>&1") | crontab -
```

## 8. サーバーモード（オプション・高速化）

Playwright 接続を維持して、キャプチャを約20%高速化。

```bash
# サーバー起動
shayde server start

# 状態確認
shayde server status
# 出力例:
# Server is running
#   PID: 12345
#   URL: http://127.0.0.1:9876
#   Browser connected: True

# キャプチャ（自動でサーバー経由になる）
shayde capture page https://example.com

# サーバー停止
shayde server stop
```

### Systemd でサーバーも常時起動（推奨）

```bash
sudo tee /etc/systemd/system/shayde-server.service << 'EOF'
[Unit]
Description=Shayde API Server
After=shayde.service
Requires=shayde.service

[Service]
Type=simple
WorkingDirectory=/var/www/shayde
ExecStart=/var/www/shayde/venv/bin/shayde server start -f
Restart=always
RestartSec=5
Environment="PATH=/var/www/shayde/venv/bin:/usr/local/bin:/usr/bin:/bin"

[Install]
WantedBy=multi-user.target
EOF

sudo systemctl daemon-reload
sudo systemctl enable shayde-server
sudo systemctl start shayde-server
```

## トラブルシューティング

### バージョン不一致エラー

```
Playwright version mismatch:
  - server version: v1.48
  - client version: v1.57
```

**解決:** Dockerfile と .shayde.yaml の `playwright_version` を pip のバージョンに合わせて再ビルド。

```bash
# バージョン確認
pip show playwright | grep Version

# Dockerfile 修正後
shayde docker build -f
shayde docker start
```

### docker compose エラー

```
docker: 'compose' is not a docker command
```

**解決:** [1. Docker Compose プラグインのインストール](#1-docker-compose-プラグインのインストール) を実行。

### コンテナが起動しない

```bash
# ログ確認
docker logs shayde-playwright

# 手動で削除して再起動
docker rm -f shayde-playwright
shayde docker start
```

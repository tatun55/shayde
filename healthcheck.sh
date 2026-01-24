#!/bin/bash

CONTAINER_NAME="shayde-playwright"

if docker ps --format '{{.Names}}' | grep -q "^${CONTAINER_NAME}$"; then
    echo "OK: Container running"
    exit 0
else
    echo "ERROR: Container not running"
    # 自動再起動
    cd /var/www/shayde
    source venv/bin/activate
    shayde docker start
    exit 1
fi

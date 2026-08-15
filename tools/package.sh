#!/usr/bin/env bash
# 本地打包脚本：生成 dailycreate-deploy.tar.gz，上传到服务器后解压并执行 ./deploy.sh
set -euo pipefail
cd "$(dirname "$0")/.."
OUT="dailycreate-deploy.tar.gz"
tar --exclude=.git --exclude=data --exclude=.venv --exclude='__pycache__' \
    --exclude=.pytest_cache --exclude='*.pyc' \
    -czf "$OUT" \
    app static tests tools \
    requirements.txt requirements-dev.txt \
    Dockerfile docker-compose.yml Caddyfile render.yaml \
    .env.example .gitignore README.md deploy.sh
echo "已生成 ${OUT}（$(du -h "$OUT" | cut -f1)）"

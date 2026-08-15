#!/usr/bin/env bash
# 服务器端一键部署脚本：在项目目录下执行 ./deploy.sh
set -euo pipefail
cd "$(dirname "$0")"

echo "==> 检查 Docker"
if ! command -v docker >/dev/null 2>&1; then
  echo "错误：未安装 Docker。请先安装 Docker 及 compose 插件。"
  exit 1
fi
if ! docker compose version >/dev/null 2>&1; then
  echo "错误：需要 Docker Compose v2（docker compose 命令）。"
  exit 1
fi

echo "==> 准备 .env"
if [ ! -f .env ]; then
  read -r -p "请输入你的域名（需已解析到本服务器，例如 checkin.example.com）: " DOMAIN
  [ -n "$DOMAIN" ] || { echo "域名不能为空"; exit 1; }
  SECRET=$(openssl rand -hex 32)
  cat > .env <<ENVEOF
DOMAIN=$DOMAIN
SESSION_SECRET=$SECRET
VAPID_SUBJECT=mailto:admin@example.com
ENVEOF
  chmod 600 .env
  echo "已生成 .env（SESSION_SECRET 为随机生成）"
else
  echo ".env 已存在，跳过生成"
fi

echo "==> 构建并启动"
docker compose up -d --build

echo ""
echo "=============================================="
echo " 部署完成！"
echo " 访问地址：https://$(grep '^DOMAIN=' .env | head -1 | cut -d= -f2)"
echo " 首次注册的第一个账号即为管理员。"
echo " 提示：请确认服务器安全组/防火墙已放行 80 和 443 端口，"
echo "      且域名 DNS 已解析到本机公网 IP（Caddy 会自动申请证书）。"
echo "=============================================="

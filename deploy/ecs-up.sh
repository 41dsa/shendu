#!/usr/bin/env bash
# 在阿里云 ECS 上安装 Docker 并启动生产编排。
# 安全组需放行 22、80。大陆地域用域名对外提供网站前需要 ICP 备案。
#
#   sudo bash deploy/ecs-up.sh --email you@example.com
#   sudo bash deploy/ecs-up.sh --email you@example.com --origin http://公网IP
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

EMAIL=""
ORIGIN=""
while [ "$#" -gt 0 ]; do
  case "$1" in
    --email)
      EMAIL="${2:-}"
      shift 2
      ;;
    --origin)
      ORIGIN="${2:-}"
      shift 2
      ;;
    *)
      echo "未知参数: $1"
      exit 1
      ;;
  esac
done

if [ "$(id -u)" -ne 0 ]; then
  echo "请用 root 执行: sudo bash deploy/ecs-up.sh --email you@example.com"
  exit 1
fi

if ! command -v docker >/dev/null 2>&1 || ! docker compose version >/dev/null 2>&1; then
  if ! command -v curl >/dev/null 2>&1; then
    if command -v apt-get >/dev/null 2>&1; then
      apt-get update
      apt-get install -y ca-certificates curl
    elif command -v dnf >/dev/null 2>&1; then
      dnf install -y curl ca-certificates
    else
      yum install -y curl ca-certificates
    fi
  fi
  if ! DOWNLOAD_URL="https://mirrors.aliyun.com/docker-ce" curl -fsSL https://get.docker.com | sh; then
    curl -fsSL https://get.docker.com | sh
  fi
  systemctl enable --now docker
fi

if [ -z "$ORIGIN" ]; then
  ORIGIN="$(curl -fsS --max-time 2 http://100.100.100.200/latest/meta-data/eipv4 || true)"
  ORIGIN="${ORIGIN//$'\r'/}"
  case "$ORIGIN" in
    ""|*Error*|*404*|*xml*)
      echo "没有读到公网 IP。请追加 --origin http://你的公网IP"
      exit 1
      ;;
  esac
  ORIGIN="http://${ORIGIN}"
fi

if [ ! -f .env ]; then
  POSTGRES_PASSWORD="$(openssl rand -hex 24)"
  umask 077
  cat > .env <<EOF
POSTGRES_PASSWORD=${POSTGRES_PASSWORD}
PUBLIC_ORIGIN=${ORIGIN}
WEB_PORT=80
EOF
  echo "已写入 ${ROOT}/.env"
else
  echo "保留已有 ${ROOT}/.env"
fi

if [ ! -f services/api/.env ]; then
  if [ -z "$EMAIL" ]; then
    echo "首次启动请指定管理员邮箱: --email you@example.com"
    exit 1
  fi
  umask 077
  cat > services/api/.env <<EOF
DATABASE_URL=sqlite:///./shendu_dev.db
JWT_SECRET=$(openssl rand -hex 32)
MASTER_KEY=$(openssl rand -hex 32)
CORS_ORIGINS=${ORIGIN}
BOOTSTRAP_ADMIN_EMAIL=${EMAIL}
AFDIAN_PLAN_URL=https://afdian.net/@your-page
MAX_CONCURRENT_GRADING_JOBS_PER_USER=2
EOF
  echo "已写入 ${ROOT}/services/api/.env"
  echo "管理员邮箱: ${EMAIL}（用这个邮箱注册才会成为管理员）"
else
  echo "保留已有 ${ROOT}/services/api/.env"
fi

if command -v firewall-cmd >/dev/null 2>&1 && systemctl is-active --quiet firewalld; then
  firewall-cmd --permanent --add-port=80/tcp
  firewall-cmd --permanent --add-port=443/tcp
  firewall-cmd --reload
fi

docker compose -f docker-compose.prod.yml up -d --build
echo "已启动。浏览器打开 ${ORIGIN}"
echo "注册后兑换激活码 TEST-DEV-LICENSE。请把 .env 与 services/api/.env 另行备份，不要提交到 git。"

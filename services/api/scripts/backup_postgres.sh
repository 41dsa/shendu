#!/usr/bin/env bash
# OPS-702：生产 Postgres 备份。在仓库根目录、docker compose 已启动时执行。
set -euo pipefail
REPO="$(cd "$(dirname "$0")/../.." && pwd)"
STAMP="$(date +%Y%m%d-%H%M%S)"
DEST="${BACKUP_DIR:-$REPO/backups}"
COMPOSE_FILE="${COMPOSE_FILE:-$REPO/docker-compose.prod.yml}"
POSTGRES_USER="${POSTGRES_USER:-shendu}"
POSTGRES_DB="${POSTGRES_DB:-shendu}"
mkdir -p "$DEST"
OUT="$DEST/shendu-${STAMP}.sql"
docker compose -f "$COMPOSE_FILE" exec -T db \
  pg_dump -U "$POSTGRES_USER" -d "$POSTGRES_DB" --no-owner --no-acl > "$OUT"
echo "Backed up to $OUT"

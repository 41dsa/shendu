#!/usr/bin/env bash
# OPS-702：SQLite 简易备份（生产 Postgres 请用 pg_dump + 保留策略）
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
DB="${DATABASE_URL:-sqlite:///./shendu_dev.db}"
DB_FILE="${DB#sqlite:///}"
STAMP="$(date +%Y%m%d-%H%M%S)"
DEST="${ROOT}/backups"
mkdir -p "$DEST"
cp "$ROOT/$DB_FILE" "$DEST/shendu-${STAMP}.db"
echo "Backed up to $DEST/shendu-${STAMP}.db"

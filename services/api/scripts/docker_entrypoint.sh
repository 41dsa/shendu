#!/bin/sh
# 生产 API 容器：RUN_INIT_DB=1 时先等数据库，再执行 init_db，然后启动传入的命令。
set -eu

if [ "${RUN_INIT_DB:-0}" = "1" ]; then
  python scripts/wait_for_db.py
  python scripts/init_db.py
fi

exec "$@"

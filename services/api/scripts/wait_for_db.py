"""Block until DATABASE_URL accepts a connection. SQLite returns immediately."""

import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sqlalchemy import create_engine, text

from app.config import settings


def main() -> None:
    url = settings.database_url
    if url.startswith("sqlite"):
        return
    engine = create_engine(url, pool_pre_ping=True)
    last_error = "unknown"
    for attempt in range(1, 61):
        try:
            with engine.connect() as conn:
                conn.execute(text("SELECT 1"))
            print("database ready", flush=True)
            return
        except Exception as exc:
            last_error = exc.__class__.__name__
            print(f"waiting for database ({attempt}/60)", flush=True)
            time.sleep(2)
    raise SystemExit(f"database not ready: {last_error}")


if __name__ == "__main__":
    main()

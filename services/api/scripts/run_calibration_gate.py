#!/usr/bin/env python3
"""运维：打印 V3 校准门禁（金标 QWK + 锚多评）。"""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.database import SessionLocal
from app.services.trait_calibration_service import calibration_dashboard


def main() -> None:
    db = SessionLocal()
    try:
        report = calibration_dashboard(db)
        print(json.dumps(report, ensure_ascii=False, indent=2))
        if not report.get("overall_gate_passed"):
            sys.exit(1)
    finally:
        db.close()


if __name__ == "__main__":
    main()

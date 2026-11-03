#!/usr/bin/env python3
"""DEP-01/02：批改 read path 禁止采分点池引擎，Trait V1 为默认脊柱。"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


def main() -> None:
    from app.config import settings
    from app.services.scoring_engine import orchestrator

    assert settings.layered_scoring_engine_enabled is True
    assert settings.grading_point_pool_engine_allowed is False
    assert "run_scoring_engine" in dir(orchestrator)
    src = Path(orchestrator.__file__).read_text(encoding="utf-8")
    assert "build_engine_result" in src or "v1_engine" in src
    assert "load_point_pool_for_level" not in src

    from app.services.scoring_engine import feedback_log

    assert "persist_trait_scoring_records" in dir(feedback_log)
    doc = feedback_log.persist_point_hit_logs.__doc__ or ""
    assert "废弃" in doc or "deprecated" in doc.lower()

    print("verify_prd_dep_guard: OK")


if __name__ == "__main__":
    main()

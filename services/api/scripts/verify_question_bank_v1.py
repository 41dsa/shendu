#!/usr/bin/env python3
"""Q-01～Q-02：题库 A 类字段 + 标准卡关联验收。"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.database import SessionLocal
from app.domain.essay import DEMO_QUESTION_ID
from app.models.entities import Question
from app.services.standard_engine.essay_item_import_service import ESSAY_ITEM_V1_KEY
from app.services.standard_engine.question_standard_link import standard_link_for_question


def _prompt_material_ok(q: Question) -> tuple[bool, str]:
    ms = dict(q.material_structured or {})
    item = ms.get(ESSAY_ITEM_V1_KEY) or {}
    prompt = str(item.get("prompt") or q.prompt or "").strip()
    material = str(item.get("material") or q.material or "").strip()
    if not prompt:
        return False, "missing prompt"
    if ms.get("genre") != "essay" and not prompt:
        return False, "not essay genre"
    return True, material[:40] or "(no material)"


def main() -> None:
    db = SessionLocal()
    try:
        q = db.get(Question, DEMO_QUESTION_ID)
        assert q, f"{DEMO_QUESTION_ID} missing — run init_db"
        ok, detail = _prompt_material_ok(q)
        assert ok, detail

        link = standard_link_for_question(db, DEMO_QUESTION_ID)
        assert link["has_active_standard"], "demo question should have published standard"

        checked = 0
        for row in db.query(Question).limit(80).all():
            ms = dict(row.material_structured or {})
            if ms.get("genre") != "essay" and "essay" not in (row.prompt or ""):
                continue
            p_ok, _ = _prompt_material_ok(row)
            assert p_ok, row.id
            checked += 1

        print(f"verify_question_bank_v1: OK (demo + {checked} essay rows)")
    finally:
        db.close()


if __name__ == "__main__":
    main()

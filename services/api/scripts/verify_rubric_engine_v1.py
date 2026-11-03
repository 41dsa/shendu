"""R-01/R-02：Trait Rubric JSON 完整性（8×L0～L4）。"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.domain.scoring_engine.rubric_loader import assert_rubric_complete, load_trait_rubric_document


def main() -> None:
    assert_rubric_complete()
    doc = load_trait_rubric_document()
    traits = doc.get("traits") or {}
    for i in range(1, 9):
        tid = f"T{i}"
        assert tid in traits, tid
        levels = traits[tid].get("levels") or {}
        for lv in ("L0", "L1", "L2", "L3", "L4"):
            assert str(levels.get(lv) or "").strip(), f"{tid} {lv}"
        assert len(traits[tid].get("plus_conditions") or []) >= 1, tid
        assert len(traits[tid].get("minus_conditions") or []) >= 1, tid
    print("verify_rubric_engine_v1: ok")


if __name__ == "__main__":
    main()

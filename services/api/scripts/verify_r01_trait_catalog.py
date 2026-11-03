#!/usr/bin/env python3
"""R-01：八大 Trait 定义与 PRD Rubric JSON 一致（代码仅从配置加载）。"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.domain.scoring_engine.rubric_loader import assert_rubric_complete, load_trait_rubric_document, trait_catalog_row
from app.domain.scoring_engine.trait_definitions import TRAIT_SPECS


def main() -> None:
    assert_rubric_complete()
    doc = load_trait_rubric_document()
    traits = doc.get("traits") or {}
    assert len(traits) == 8
    for tid, spec in TRAIT_SPECS.items():
        row = trait_catalog_row(tid)
        assert row.get("name") == spec.name, tid
        assert row.get("standard_tier") == spec.standard_tier, tid
        assert bool(row.get("participates_in_score")) == spec.participates_in_score, tid
        assert list(row.get("dimension_ids") or []) == list(spec.dimension_ids), tid
        levels = row.get("levels") or {}
        assert len(levels) == 5, tid
    scorable = [t for t, s in TRAIT_SPECS.items() if s.participates_in_score]
    assert set(scorable) == {"T1", "T3", "T4", "T5", "T8"}
    print("verify_r01_trait_catalog: OK")


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""R-04：同类输入 Rubric 定级稳定（trait_level_from_rubric 确定性）。"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.domain.scoring_engine.evidence_engine import TraitEvidenceBundle
from app.domain.scoring_engine.rubric_engine import trait_level_from_rubric


def main() -> None:
    bundle = TraitEvidenceBundle(trait_id="T5", positive=["观点明确，论证链条完整"], grounding_rate=0.9)
    essay = "因此推进基层治理现代化，观点明确，论证链条完整。"
    a = trait_level_from_rubric("T5", heuristic_level="L2", bundle=bundle, essay=essay)
    b = trait_level_from_rubric("T5", heuristic_level="L2", bundle=bundle, essay=essay)
    assert a == b
    assert a in ("L2", "L3", "L4")
    print("verify_rubric_level_stability: ok")


if __name__ == "__main__":
    main()

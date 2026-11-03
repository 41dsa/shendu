#!/usr/bin/env python3
"""V3-MODEL：路由 stub 冒烟（默认关闭无 trace；开启时 passthrough + trace）。"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.config import settings
from app.domain.scoring_engine.trait_definitions import TraitDiagnostic, TraitEvidence
from app.services.scoring_engine.v3_model_router import maybe_apply_v3_trait_model


def _one() -> TraitDiagnostic:
    return TraitDiagnostic(
        trait_id="T1",
        name="立意",
        standard_tier="B",
        level="L2",
        participates_in_score=True,
        confidence=0.8,
        evidence=TraitEvidence(positive=[], negative=[], missing=[]),
    )


def main() -> None:
    orig = settings.v3_trait_model_enabled
    try:
        settings.v3_trait_model_enabled = False
        _, traces_off = maybe_apply_v3_trait_model([_one()])
        assert traces_off == []

        settings.v3_trait_model_enabled = True
        diags, traces_on = maybe_apply_v3_trait_model([_one()])
        assert len(diags) == 1 and diags[0].level == "L2"
        assert len(traces_on) == 1 and traces_on[0].layer == "v3_trait_model"
    finally:
        settings.v3_trait_model_enabled = orig

    print("verify_v3_model_router: OK")


if __name__ == "__main__":
    main()

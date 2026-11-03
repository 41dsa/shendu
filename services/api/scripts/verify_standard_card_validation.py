#!/usr/bin/env python3
"""M-01/M-02 标准卡字段校验。"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.schemas.standard_card_v1 import StandardCardV1Schema, ThesisSpaceV1
from app.services.standard_engine.standard_card_validation import standard_card_validation_errors


def main() -> None:
    ok = StandardCardV1Schema(
        question_id="q1",
        theme="基层治理",
        proposition_task="论证",
        keywords=["基层", "治理"],
        keyword_relations=[{"a": "基层", "b": "治理", "relation": "主题"}],
        core_problem="矛盾",
        thesis_space=ThesisSpaceV1(core=["治理现代化"]),
        material_sentence_anchors=["网格化"],
    )
    assert standard_card_validation_errors(ok, for_publish=True) == []

    bad = StandardCardV1Schema(question_id="q2", proposition_task="", keywords=[])
    errs = standard_card_validation_errors(bad, for_publish=True)
    assert any("M-01" in e for e in errs)

    kw_only = StandardCardV1Schema(
        question_id="q3",
        proposition_task="写",
        keywords=["a", "b"],
        core_problem="x",
        thesis_space=ThesisSpaceV1(core=["y"]),
    )
    warn = standard_card_validation_errors(kw_only, for_publish=True)
    assert any("M-02" in e for e in warn)

    print("verify_standard_card_validation: OK")


if __name__ == "__main__":
    main()

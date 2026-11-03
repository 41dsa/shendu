"""M-11～M-12：三模型标准卡共识合并（mock，无 LLM）。"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.schemas.standard_card_v1 import StandardCardV1Schema, ThesisSpaceV1
from app.services.standard_engine.standard_consensus_pipeline import merge_standard_cards_v1


def _card(kw: list[str], theme: str, core: list[str]) -> StandardCardV1Schema:
    return StandardCardV1Schema(
        question_id="q1",
        keywords=kw,
        theme=theme,
        proposition_task="论证观点",
        thesis_space=ThesisSpaceV1(core=core),
    )


def main() -> None:
    c1 = _card(["基层治理", "现代化"], "基层治理", ["以治理体系和能力现代化推进基层治理"])
    c2 = _card(["基层治理", "数字化"], "基层治理", ["以治理体系和能力现代化推进基层治理"])
    c3 = _card(["基层治理", "网格化"], "基层治理", ["以数字化赋能基层治理"])
    merged, meta = merge_standard_cards_v1([c1, c2, c3])
    assert "基层治理" in merged.keywords
    assert meta.consensus_score > 0.5
    assert meta.model_count == 3
    assert merged.review_status in ("draft", "published")
    assert merged.dispute_marks

    agree = merge_standard_cards_v1([c1, c1, c1])[0]
    assert agree.review_status == "published"
    print("verify_standard_consensus_3model: ok")


if __name__ == "__main__":
    main()

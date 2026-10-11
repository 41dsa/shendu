"""生产与评测引擎 V1 对齐冒烟。"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.domain.standard_engine.criterion_confidence import enrich_rubric_contract, criterion_usage_band
from app.domain.standard_engine.validation import run_standard_validators
from app.models.entities import Question, QuestionType
from app.services.standard_engine.question_parse import parse_essay_question_metadata


def main() -> None:
    assert criterion_usage_band(0.9) == "high"
    assert criterion_usage_band(0.75) == "medium"
    assert criterion_usage_band(0.5) == "low"

    rubric = enrich_rubric_contract(
        {
            "total_score": 10,
            "dimensions": [{"id": "D01", "label": "立意", "max_score": 10, "criteria": ["RC1"]}],
            "criteria": [
                {
                    "id": "RC1",
                    "dimension_id": "D01",
                    "core": "立意鲜明",
                    "max_score": 10,
                    "confidence": 0.92,
                }
            ],
            "loss_rules": [],
        }
    )
    assert rubric["criteria"][0].get("score_min") is not None
    v = run_standard_validators(
        question_standard={"focus_points": ["扣题", "联系材料"]},
        rubric=rubric,
        prompt_text="请结合给定材料，围绕「测试主题」自拟题目写一篇文章，800～1000字。",
        reference_coverage_ratio=1.0,
    )
    assert v.get("criterion_confidence_tiers"), v
    assert v.get("overall_passed"), v

    q = Question(
        id="t",
        title="2024国考副省级：测试",
        question_type=QuestionType.essay,
        score=40,
        word_limit=1200,
        prompt="写一篇文章",
        material_structured={"exam": "国考副省级", "year": 2024, "word_min": 1000, "word_max": 1200},
    )
    meta = parse_essay_question_metadata(q)
    assert meta["question_type"] == "essay"
    assert meta["category"] == "副省级"
    print("verify_prod_eval_alignment: ok")


if __name__ == "__main__":
    main()

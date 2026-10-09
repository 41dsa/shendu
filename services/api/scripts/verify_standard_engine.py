"""STD-109：标准引擎 schema 与验证器冒烟测试。"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.domain.standard_engine.confidence import compute_confidence_score, confidence_band
from app.domain.standard_engine.validation import run_standard_validators
from app.schemas.standard_engine import QuestionStandardSchema, RubricStandardSchema


def main() -> None:
    components = {
        "source_trust": 0.9,
        "prompt_trace": 0.95,
        "reference_support": 0.88,
        "model_agreement": 0.85,
        "ability_alignment": 1.0,
    }
    score = compute_confidence_score(components)
    assert score >= 0.85, score
    assert confidence_band(score) in ("high", "medium_high")

    q = QuestionStandardSchema(
        question_id="test-q",
        focus_points=["扣题"],
        keywords=["治理"],
    )
    rubric = RubricStandardSchema(
        question_id="test-q",
        total_score=40,
        dimensions=[
            {"id": "D01", "label": "立意与观点", "max_score": 10, "ability": "A1", "criteria": ["RC1"]},
            {"id": "D02", "label": "结构与层次", "max_score": 10, "ability": "A2", "criteria": []},
            {"id": "D03", "label": "论证与素材", "max_score": 10, "ability": "A3", "criteria": []},
            {"id": "D04", "label": "语言表达", "max_score": 10, "ability": "A4", "criteria": []},
        ],
        criteria=[
            {
                "id": "RC1",
                "dimension_id": "D01",
                "ability_id": "A1",
                "core": "立意扣题",
                "confidence": 0.9,
            }
        ],
    )
    out = run_standard_validators(
        question_standard=q.model_dump(),
        rubric=rubric.model_dump(),
        prompt_text="请围绕「基层治理现代化」主题，联系实际，自选角度，写一篇文章。要求观点明确、论证充分，800～1000字。",
    )
    assert out["overall_passed"], out
    print("verify_standard_engine: ok")


if __name__ == "__main__":
    main()

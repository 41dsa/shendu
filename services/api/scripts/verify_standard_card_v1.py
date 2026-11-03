"""PRD §4.2 标准卡 V1 schema 与 builder 冒烟。"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.domain.essay_grading_context import EssayGradingContext
from app.domain.question_type import QuestionType
from app.domain.scoring_engine.question_standard_card import build_question_standard_card
from app.schemas.standard_card_v1 import StandardCardV1Schema, standard_card_v1_from_legacy


def main() -> None:
    legacy = {
        "proposition_task": "围绕基层治理写议论文",
        "keywords": ["基层治理"],
        "thesis_scope": {"must_address": ["治理现代化"], "must_avoid": ["完全偏题方向"]},
        "review_status": "published",
        "version": 2,
        "core_problem": "如何推进基层治理现代化",
        "material_sentence_anchors": ["网格化管理"],
        "trait_rubric_adjustments": [{"trait_id": "T1", "weight_override": 0.3}],
    }
    v1 = standard_card_v1_from_legacy("q1", legacy)
    assert v1.schema_version == "standard_card_v1"
    assert v1.thesis_space.core == ["治理现代化"]
    assert v1.review_status == "published"

    full = StandardCardV1Schema.model_validate(
        {
            "question_id": "q2",
            "standard_version": 1,
            "review_status": "published",
            "theme": "测试题",
            "proposition_task": "论证",
            "keywords": ["关键词"],
            "keyword_relations": [{"a": "基层", "b": "治理", "relation": "主题"}],
            "core_problem": "矛盾",
            "thesis_space": {
                "core": ["立意"],
                "acceptable": ["可接受"],
                "edge_acceptable": ["边缘"],
                "off_topic": ["偏题"],
                "severe_off_topic": ["跑题"],
            },
            "material_facts": [{"fact": "事实1", "source_anchor": "材料句"}],
            "material_logic": ["因果链"],
            "recommended_argument_directions": ["分论点方向"],
            "recommended_analysis_dimensions": ["分析维度"],
            "recommended_policy_directions": ["对策方向"],
            "material_sentence_anchors": ["锚点句"],
            "trait_rubric_adjustments": [{"trait_id": "T5", "interval_span_factor": 1.2}],
            "dispute_marks": ["立意存在标准依赖"],
        }
    )
    assert full.material_facts[0].fact == "事实1"

    ctx = EssayGradingContext(
        title="题",
        prompt="写一篇文章",
        reference_material="材料：网格化管理",
        material_structured=None,
        scoring_points=[],
        score=40,
        word_limit=1200,
        question_type=QuestionType.essay,
        cache_context_key="q1",
        question_id="q1",
        question_standard=legacy,
        standard_version=2,
        standard_review_status="published",
    )
    card = build_question_standard_card(ctx)
    assert card.reviewed is True
    assert card.core_problem == "如何推进基层治理现代化"
    assert card.trait_rubric_adjustments
    print("verify_standard_card_v1: ok")


if __name__ == "__main__":
    main()

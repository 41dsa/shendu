#!/usr/bin/env python3
"""M-03/06/07/08：标准卡 material  enrichment 冒烟。"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.schemas.standard_engine import MaterialAnalysisSchema, QuestionStandardSchema, ThesisScopeSchema
from app.services.standard_engine.standard_card_enrich import enrich_card_payload_from_job_context
from app.services.standard_engine.standard_consensus_pipeline import card_from_question_standard


def main() -> None:
    qid = "demo-enrich-001"
    q_std = QuestionStandardSchema(
        question_id=qid,
        proposition_task="围绕基层治理写一篇文章",
        thesis_scope=ThesisScopeSchema(
            must_address=["基层治理", "现代化"],
            must_avoid=["偏题：仅谈经济而忽略治理", "跑题：与材料无关"],
        ),
        keywords=["基层治理", "现代化"],
    )
    mat = MaterialAnalysisSchema(
        question_id=qid,
        themes=["基层治理现代化", "网格化管理"],
        facts=[{"fact": "某市推进网格化服务", "source": "材料1"}],
        usable_for_argument=["制度创新", "科技赋能"],
        viewpoints=[{"viewpoint": "治理重心下移", "implication": "提升响应速度"}],
    )
    card = card_from_question_standard(qid, q_std)
    payload = {
        "standard_card_v1": card.model_dump(),
        "consensus_score": 1.0,
        "model_labels": ["test"],
    }
    rubric = {"criteria": [{"dimension_id": "D01", "confidence": 0.7}]}
    out = enrich_card_payload_from_job_context(qid, payload, q_std=q_std, mat=mat, rubric=rubric)
    assert out.get("material_enriched") is True
    sc = out["standard_card_v1"]
    assert sc.get("core_problem")
    assert sc.get("material_facts")
    assert sc.get("material_logic")
    assert sc.get("recommended_argument_directions")
    assert sc.get("keyword_relations") or len(sc.get("keywords") or []) < 2
    assert sc.get("trait_rubric_adjustments")
    ts = sc.get("thesis_space") or {}
    assert ts.get("core"), ts
    print("verify_standard_card_enrich: OK")


if __name__ == "__main__":
    main()

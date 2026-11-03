"""PRD V1 完全实现 — 阶段性合规门禁（Phase 0/1 起）。"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


def main() -> None:
    from app.domain.scoring_engine.rubric_loader import assert_rubric_complete, rubric_version
    from app.schemas.standard_card_v1 import StandardCardV1Schema

    assert_rubric_complete()
    assert rubric_version().startswith("essay-trait"), rubric_version()

    required_fields = set(StandardCardV1Schema.model_fields.keys())
    for name in (
        "keyword_relations",
        "core_problem",
        "thesis_space",
        "material_facts",
        "trait_rubric_adjustments",
        "review_status",
        "dispute_marks",
    ):
        assert name in required_fields, name

    # 子脚本
    import verify_evidence_grounding
    import verify_multi_standard_views
    import verify_score_display_policy
    import verify_trait_report_spine
    import verify_weak_supervision_factory
    import verify_anchor_scale
    import verify_prd_metrics_gate
    import verify_boundary_policy
    import verify_report_json_schema
    import verify_rubric_engine_v1
    import verify_r01_trait_catalog
    import verify_rubric_level_stability
    import verify_standard_consensus_3model
    import verify_standard_consensus_pipeline_integration
    import verify_v2_ws_anchor
    import verify_v3_calibration_gate
    import verify_standard_card_review
    import verify_anchor_admin_api
    import verify_question_standard_link
    import verify_essay_item_import
    import verify_scoring_engine
    import verify_standard_card_v1
    import verify_trait_scoring_engine
    import verify_trait_vote_merge
    import verify_standard_card_enrich
    import verify_evidence_accuracy
    import verify_v3_model_router
    import verify_question_bank_v1
    import verify_trait_voting_3model
    import verify_standard_card_validation
    import verify_material_anchor_evidence
    import verify_pair_rank_consistency
    import verify_trait_vote_evidence_merge
    import verify_boundary_policy_matrix
    import verify_hard_rules_deterministic
    import verify_hard_rules_a04_a06
    import verify_trait_evidence_decouple
    import verify_retry_active_learning
    import verify_al06_dispute_pool
    import verify_prd_dep_guard
    import verify_trait_scoring_records
    import verify_anchor_pair_spearman_db
    import verify_standard_match_confidence
    import verify_rep05_structured_suggestions
    import verify_rep01_diagnostic_seven
    import verify_w01_w03_weak_labels
    import verify_w07_retry_weak_label
    import verify_a03_scope_hard_rules
    import verify_dep03_point_pool_optional
    import verify_trait_gold_regression
    import verify_requirement_scoring

    verify_scoring_engine.main()
    verify_standard_card_v1.main()
    verify_trait_scoring_engine.main()
    verify_trait_vote_merge.main()
    verify_evidence_grounding.main()
    verify_multi_standard_views.main()
    verify_score_display_policy.main()
    verify_trait_report_spine.main()
    verify_weak_supervision_factory.main()
    verify_anchor_scale.main()
    verify_prd_metrics_gate.main()
    verify_boundary_policy.main()
    verify_report_json_schema.main()
    verify_rubric_engine_v1.main()
    verify_r01_trait_catalog.main()
    verify_rubric_level_stability.main()
    verify_standard_consensus_3model.main()
    verify_standard_consensus_pipeline_integration.main()
    verify_v2_ws_anchor.main()
    verify_v3_calibration_gate.main()
    verify_standard_card_review.main()
    verify_anchor_admin_api.main()
    verify_question_standard_link.main()
    verify_essay_item_import.main()
    verify_standard_card_enrich.main()
    verify_evidence_accuracy.main()
    verify_v3_model_router.main()
    verify_question_bank_v1.main()
    verify_trait_voting_3model.main()
    verify_standard_card_validation.main()
    verify_material_anchor_evidence.main()
    verify_pair_rank_consistency.main()
    verify_trait_vote_evidence_merge.main()
    verify_boundary_policy_matrix.main()
    verify_hard_rules_deterministic.main()
    verify_hard_rules_a04_a06.main()
    verify_trait_evidence_decouple.main()
    verify_retry_active_learning.main()
    verify_al06_dispute_pool.main()
    verify_prd_dep_guard.main()
    verify_trait_scoring_records.main()
    verify_anchor_pair_spearman_db.main()
    verify_standard_match_confidence.main()
    verify_rep05_structured_suggestions.main()
    verify_rep01_diagnostic_seven.main()
    verify_w01_w03_weak_labels.main()
    verify_w07_retry_weak_label.main()
    verify_a03_scope_hard_rules.main()
    verify_dep03_point_pool_optional.main()
    verify_trait_gold_regression.main()
    verify_requirement_scoring.main()

    print("verify_prd_v1_compliance: phase0/1/2/3/4/5/6+ gate ok")


if __name__ == "__main__":
    main()

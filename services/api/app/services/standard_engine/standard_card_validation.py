"""M-01/M-02：StandardCardV1 发布前字段校验。"""

from __future__ import annotations

from app.schemas.standard_card_v1 import StandardCardV1Schema


def standard_card_validation_errors(
    card: StandardCardV1Schema,
    *,
    for_publish: bool = True,
) -> list[str]:
    errors: list[str] = []
    if not str(card.proposition_task or "").strip():
        errors.append("M-01: proposition_task 不能为空")
    if not str(card.theme or "").strip() and not card.keywords:
        errors.append("M-01: theme 或 keywords 至少一项")
    if for_publish:
        if not str(card.core_problem or "").strip() and not card.thesis_space.core:
            errors.append("M-03/M-04: 发布需 core_problem 或 thesis_space.core")
        if len(card.keywords) >= 2 and not card.keyword_relations:
            errors.append("M-02: keywords≥2 时建议填写 keyword_relations")
        if card.review_status == "published" and not card.material_sentence_anchors and not card.material_facts:
            errors.append("M-09: 发布建议包含 material_sentence_anchors 或 material_facts")
    return errors

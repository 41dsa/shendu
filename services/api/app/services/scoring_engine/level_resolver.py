from __future__ import annotations

from app.domain.scoring_engine.level_config import ExamLevelId
from app.services.essay_context import EssayGradingContext


def resolve_exam_level(ctx: EssayGradingContext) -> tuple[ExamLevelId, bool]:
    if ctx.exam_level:
        return ctx.exam_level, False

    inferred = True
    level: ExamLevelId = "municipal"
    texts: list[str] = []
    if ctx.material_structured:
        texts.append(str(ctx.material_structured.get("exam") or ""))
    if ctx.exam_policy:
        texts.append(str(ctx.exam_policy.get("exam_label") or ""))
        texts.append(str(ctx.exam_policy.get("category") or ""))
    texts.append(ctx.title or "")
    blob = " ".join(texts)
    if "行政执法" in blob or ("执法" in blob and "行政" in blob):
        level = "enforcement"
        inferred = "行政执法" not in blob
    elif "副省级" in blob or "中央机关" in blob:
        level = "provincial"
        inferred = "副省级" not in blob
    elif "市地级" in blob or "县乡" in blob:
        level = "municipal"
        inferred = False
    return level, inferred

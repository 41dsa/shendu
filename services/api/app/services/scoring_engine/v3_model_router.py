"""V3-MODEL：专用 Trait 模型路由（stub：开关开启时记录 trace，仍走 V1 规则+LLM 脊柱）。"""

from __future__ import annotations

from app.config import settings
from app.domain.scoring_engine.trait_definitions import TraitDiagnostic
from app.domain.scoring_engine.types import EngineLayerTrace


def maybe_apply_v3_trait_model(
    diagnostics: list[TraitDiagnostic],
) -> tuple[list[TraitDiagnostic], list[EngineLayerTrace]]:
    if not settings.v3_trait_model_enabled:
        return diagnostics, []
    levels = {d.trait_id: d.level for d in diagnostics}
    trace = EngineLayerTrace(
        layer="v3_trait_model",
        detail="stub_passthrough",
        data={
            "model_id": settings.v3_trait_model_id,
            "trait_levels": levels,
            "note": "V3 专用模型未接入，输出与 V1 一致",
        },
    )
    return diagnostics, [trace]

from __future__ import annotations

import re
from typing import Any

from app.schemas.point_pool import ExamLevelId

_STRUCTURE_MARKERS = {
    "转折": ("但是", "然而", "不过", "却", "尽管"),
    "因果": ("因此", "所以", "因而", "导致", "由于"),
    "并列": ("同时", "此外", "另外", "一方面", "另一方面"),
    "问题": ("问题", "困境", "矛盾", "挑战", "短板"),
    "对策": ("应", "需要", "必须", "举措", "路径", "机制"),
    "影响": ("影响", "作用", "意义", "价值"),
}

_LEVEL_FOCUS: dict[ExamLevelId, str] = {
    "provincial": "宏观分析、辩证思维、理论深度",
    "municipal": "具体执行、基层落地、对策可行",
    "enforcement": "法治思维、公共服务、规范执法",
}


def extract_candidates_l1(
    *,
    prompt: str,
    material_paras: list[dict[str, Any]],
    rubric_criteria: list[dict[str, Any]],
    focus_points: list[str],
    themes: list[str],
    level_id: ExamLevelId,
    reference_excerpts: list[str] | None = None,
) -> list[dict[str, Any]]:
    """L1 多策略候选采分点（A 结构信号 + B rubric 回填 + C 主题/焦点 + D 参考弱监督）。"""
    candidates: list[dict[str, Any]] = []
    focus_hint = _LEVEL_FOCUS.get(level_id, "")

    for para in material_paras:
        pid = int(para["para_id"])
        text = str(para["text"])
        for signal_type, words in _STRUCTURE_MARKERS.items():
            for w in words:
                if w not in text:
                    continue
                idx = text.find(w)
                snippet = text[max(0, idx - 8) : min(len(text), idx + 48)].strip()
                if len(snippet) < 6:
                    continue
                candidates.append(
                    {
                        "text": snippet,
                        "keywords": [w],
                        "source_para": [pid],
                        "extraction_method": f"structure_{signal_type}",
                        "point_type": "sub" if signal_type != "问题" else "main",
                        "level_focus": focus_hint,
                    }
                )

    for i, c in enumerate(rubric_criteria or []):
        if not isinstance(c, dict):
            continue
        core = str(c.get("core") or "").strip()
        if not core:
            continue
        kws = list(c.get("acceptable_expressions") or []) + list(c.get("observable_signals") or [])
        candidates.append(
            {
                "text": core,
                "keywords": [str(k) for k in kws if k][:8],
                "source_para": [],
                "extraction_method": "rubric_backfill",
                "point_type": "main" if c.get("dimension_id") == "D01" else "sub",
                "criterion_id": c.get("id"),
                "level_focus": focus_hint,
            }
        )

    for fp in focus_points or []:
        t = str(fp).strip()
        if t:
            candidates.append(
                {
                    "text": t,
                    "keywords": [t],
                    "source_para": [],
                    "extraction_method": "focus_point",
                    "point_type": "main",
                    "level_focus": focus_hint,
                }
            )

    for theme in themes or []:
        t = str(theme).strip()
        if t:
            candidates.append(
                {
                    "text": t,
                    "keywords": [t],
                    "source_para": [],
                    "extraction_method": "theme_induction",
                    "point_type": "theme",
                    "level_focus": focus_hint,
                }
            )

    for ex in reference_excerpts or []:
        for line in re.split(r"[\n；;]", ex):
            line = line.strip()
            if len(line) >= 8:
                candidates.append(
                    {
                        "text": line[:120],
                        "keywords": [],
                        "source_para": [],
                        "extraction_method": "reference_backfill",
                        "point_type": "evidence",
                        "level_focus": focus_hint,
                    }
                )

    return _dedupe_candidates(candidates)


def _dedupe_candidates(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    seen: set[str] = set()
    out: list[dict[str, Any]] = []
    for item in items:
        key = re.sub(r"\s+", "", str(item.get("text") or ""))[:64]
        if not key or key in seen:
            continue
        seen.add(key)
        out.append(item)
    return out


def llm_role_prompts(level_id: ExamLevelId) -> list[dict[str, str]]:
    focus = _LEVEL_FOCUS.get(level_id, "")
    return [
        {"role": "proposer", "label": "命题人", "hint": f"提取应成为采分点的核心表述，侧重{focus}"},
        {"role": "grader", "label": "阅卷人", "hint": f"提取可区分档次的要点，侧重{focus}"},
        {"role": "candidate", "label": "考生", "hint": f"提取高分作文可能覆盖的要点，侧重{focus}"},
    ]

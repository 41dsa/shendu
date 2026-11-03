"""从作文原文抽取规则/Rubric 可用的结构、扣题与论证信号。"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from app.domain.scoring_engine.question_standard_card import QuestionStandardCard
from app.domain.scoring_engine.text_utils import best_paragraph_match, split_paragraphs


@dataclass
class EssaySignals:
    paragraphs: list[str]
    keyword_hits: list[str]
    keyword_coverage: float
    main_thesis_signal: bool
    off_topic_signal: bool
    structure_score: float
    argument_markers: int
    material_use_hits: list[str]
    sample_quotes: dict[str, str] = field(default_factory=dict)


_ARG_RE = re.compile(r"(因此|所以|可见|由此可见|意味着|一方面|另一方面|不仅|更|既要|也要)")


def _quote_para(paragraphs: list[str], idx: int) -> str:
    if idx < 0 or idx >= len(paragraphs):
        return ""
    t = paragraphs[idx].strip()
    return t[:120] if len(t) > 120 else t


def analyze_essay_signals(essay: str, standard: QuestionStandardCard) -> EssaySignals:
    paragraphs = split_paragraphs(essay)
    body = essay.replace("\r", "")
    keywords = standard.keywords or standard.material_anchor_phrases[:6]
    hits = [k for k in keywords if k and k in body]
    coverage = len(hits) / max(len(keywords), 1)

    core_terms = standard.core_theses + standard.acceptable_theses + hits[:4]
    main_thesis = any(t and t in body for t in core_terms) or coverage >= 0.25

    off_topic = False
    for hint in standard.severe_off_topic_hints + standard.off_topic_hints:
        if hint and hint in body:
            off_topic = True
            break

    struct = 0.35
    if len(paragraphs) >= 4:
        struct += 0.25
    if len(paragraphs) >= 6:
        struct += 0.15
    if len(paragraphs) >= 3 and len(paragraphs[0]) < 180:
        struct += 0.1
    struct = min(1.0, struct)

    arg_n = len(_ARG_RE.findall(body))
    mat_hits = [p for p in standard.material_anchor_phrases if p and p in body][:5]

    quotes: dict[str, str] = {}
    if paragraphs:
        quotes["opening"] = _quote_para(paragraphs, 0)
        if len(paragraphs) > 2:
            quotes["body"] = _quote_para(paragraphs, len(paragraphs) // 2)
        quotes["closing"] = _quote_para(paragraphs, -1)
    if keywords:
        _para_no, para_text, _sim = best_paragraph_match(body, [keywords[0]])
        if para_text:
            quotes["keyword"] = para_text[:120]

    return EssaySignals(
        paragraphs=paragraphs,
        keyword_hits=hits,
        keyword_coverage=round(coverage, 3),
        main_thesis_signal=main_thesis and not off_topic,
        off_topic_signal=off_topic or (not main_thesis and coverage < 0.08),
        structure_score=struct,
        argument_markers=arg_n,
        material_use_hits=mat_hits,
        sample_quotes=quotes,
    )

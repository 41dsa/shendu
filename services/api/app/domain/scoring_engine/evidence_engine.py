"""PRD ④ Evidence 引擎：规则抽取 + 原文子串校验（LLM 证据须过 grounding）。"""

from __future__ import annotations

import re
from dataclasses import dataclass, field, replace

from app.domain.scoring_engine.essay_signals import EssaySignals
from app.domain.scoring_engine.hard_rules import HardRuleReport
from app.domain.scoring_engine.question_standard_card import QuestionStandardCard
from app.domain.scoring_engine.trait_definitions import TRAIT_SPECS, TraitEvidence, TraitId


@dataclass
class EvidenceSpan:
    quote: str
    para: int | None = None
    start: int | None = None
    end: int | None = None
    grounded: bool = True


@dataclass
class TraitEvidenceBundle:
    trait_id: TraitId
    positive: list[str] = field(default_factory=list)
    negative: list[str] = field(default_factory=list)
    missing: list[str] = field(default_factory=list)
    spans: list[EvidenceSpan] = field(default_factory=list)
    grounding_rate: float = 1.0


@dataclass
class EvidenceEngineResult:
    by_trait: dict[str, TraitEvidenceBundle]
    overall_grounding_rate: float
    rejected_quotes: list[str] = field(default_factory=list)


def _normalize_for_match(text: str) -> str:
    return re.sub(r"\s+", "", text)


def quote_is_substring(essay: str, quote: str, *, min_len: int = 6) -> bool:
    q = (quote or "").strip()
    if len(q) < min_len:
        return False
    if q in essay:
        return True
    ne = _normalize_for_match(essay)
    nq = _normalize_for_match(q)
    return bool(nq) and nq in ne


def ground_quotes(essay: str, quotes: list[str], *, min_len: int = 6) -> tuple[list[str], list[str]]:
    """返回 (保留的原文摘录, 被拒绝的条目)。"""
    kept: list[str] = []
    rejected: list[str] = []
    seen: set[str] = set()
    for raw in quotes:
        q = str(raw or "").strip()
        if not q or q in seen:
            continue
        if quote_is_substring(essay, q, min_len=min_len):
            seen.add(q)
            kept.append(q[:160])
        else:
            rejected.append(q[:160])
    return kept, rejected


def _locate_quote(essay: str, quote: str) -> tuple[int | None, int | None, int | None]:
    if not quote:
        return None, None, None
    pos = essay.find(quote)
    if pos < 0:
        ne = _normalize_for_match(essay)
        nq = _normalize_for_match(quote)
        if nq and nq in ne:
            pos = ne.find(nq)
            if pos >= 0:
                return pos, pos + len(nq), None
        return None, None, None
    end = pos + len(quote)
    head = essay[:pos]
    para = head.count("\n\n") + 1
    return pos, end, para


def _span_from_quote(essay: str, quote: str, *, grounded: bool) -> EvidenceSpan:
    start, end, para = _locate_quote(essay, quote)
    return EvidenceSpan(quote=quote, para=para, start=start, end=end, grounded=grounded)


def merge_llm_evidence_into_bundle(
    essay: str,
    bundle: TraitEvidenceBundle,
    *,
    positive: list[str],
    negative: list[str],
    missing: list[str],
) -> TraitEvidenceBundle:
    pos_k, rej_p = ground_quotes(essay, positive)
    neg_k, rej_n = ground_quotes(essay, negative, min_len=4)
    all_rejected = rej_p + rej_n
    missing_clean = [str(m).strip() for m in missing if str(m).strip()][:4]

    merged_pos = list(dict.fromkeys(bundle.positive + pos_k))[:5]
    merged_neg = list(dict.fromkeys(bundle.negative + neg_k))[:5]
    merged_miss = list(dict.fromkeys(bundle.missing + missing_clean))[:4]

    spans: list[EvidenceSpan] = []
    for q in merged_pos + merged_neg:
        spans.append(_span_from_quote(essay, q, grounded=True))
    for q in all_rejected:
        spans.append(_span_from_quote(essay, q, grounded=False))

    emitted = len(merged_pos) + len(merged_neg)
    if emitted:
        rate = min(1.0, (len(merged_pos) + len(merged_neg)) / max(emitted, 1))
    elif all_rejected:
        rate = bundle.grounding_rate
    else:
        rate = bundle.grounding_rate

    return TraitEvidenceBundle(
        trait_id=bundle.trait_id,
        positive=merged_pos,
        negative=merged_neg,
        missing=merged_miss,
        spans=spans,
        grounding_rate=round(rate, 3),
    )


def _rule_bundle_for_trait(
    tid: TraitId,
    essay: str,
    signals: EssaySignals,
    hard: HardRuleReport,
    standard: QuestionStandardCard,
) -> TraitEvidenceBundle:
    positive: list[str] = []
    negative: list[str] = []
    missing: list[str] = []

    if tid == "T1":
        for q in signals.sample_quotes.values():
            if q:
                positive.append(q)
        if signals.keyword_hits:
            missing_from_kw = []
            for k in standard.keywords[:8]:
                if k and k not in essay and k not in signals.keyword_hits:
                    missing_from_kw.append(f"未见关键词「{k}」")
            missing.extend(missing_from_kw[:2])
        if signals.off_topic_signal:
            missing.append("偏题/跑题风险（标准卡或规则）")
    elif tid == "T3":
        if signals.paragraphs:
            positive.append(signals.sample_quotes.get("opening") or signals.paragraphs[0][:120])
        if hard.flags.get("structure_incomplete"):
            missing.append("段落过少，结构不完整")
    elif tid == "T4":
        for hit in signals.material_use_hits:
            if hit in essay:
                positive.append(hit[:120])
        for anchor in (standard.material_anchor_phrases or [])[:10]:
            a = str(anchor or "").strip()
            if not a:
                continue
            if quote_is_substring(essay, a, min_len=4):
                snippet = a if len(a) <= 120 else a[:120]
                if snippet not in positive:
                    positive.append(snippet)
            else:
                missing.append(f"未覆盖材料锚点「{a[:28]}」")
        if hard.flags.get("mechanical_copy"):
            missing.append("疑似大段机械摘抄材料")
        elif not signals.material_use_hits and not positive:
            missing.append("未见明显材料转化或材料锚点句")
    elif tid == "T5":
        body_q = signals.sample_quotes.get("body") or ""
        if body_q:
            positive.append(body_q)
        if signals.argument_markers < 3:
            missing.append("论证推进语偏少，论证链可能不完整")
    elif tid == "T8":
        if hard.format_issues:
            missing.extend(hard.format_issues[:2])
        closing = signals.sample_quotes.get("closing")
        if closing:
            positive.append(closing)

    pos_g, rej = ground_quotes(essay, positive, min_len=4)
    neg_g, rej_n = ground_quotes(essay, negative, min_len=4)
    spans = [_span_from_quote(essay, q, grounded=True) for q in pos_g + neg_g]
    for q in rej + rej_n:
        spans.append(_span_from_quote(essay, q, grounded=False))

    return TraitEvidenceBundle(
        trait_id=tid,
        positive=pos_g,
        negative=neg_g,
        missing=missing[:4],
        spans=spans,
        grounding_rate=1.0 if not (rej or rej_n) else len(pos_g + neg_g) / max(len(pos_g + neg_g + rej + rej_n), 1),
    )


def extract_rule_evidence(
    essay: str,
    signals: EssaySignals,
    hard: HardRuleReport,
    standard: QuestionStandardCard,
) -> EvidenceEngineResult:
    by_trait: dict[str, TraitEvidenceBundle] = {}
    all_rejected: list[str] = []
    rates: list[float] = []
    for tid in TRAIT_SPECS:
        b = _rule_bundle_for_trait(tid, essay, signals, hard, standard)
        by_trait[tid] = b
        rates.append(b.grounding_rate)
        for sp in b.spans:
            if not sp.grounded:
                all_rejected.append(sp.quote)
    overall = sum(rates) / len(rates) if rates else 1.0
    return EvidenceEngineResult(
        by_trait=by_trait,
        overall_grounding_rate=round(overall, 3),
        rejected_quotes=all_rejected,
    )


def bundle_to_trait_evidence(bundle: TraitEvidenceBundle) -> TraitEvidence:
    return TraitEvidence(
        positive=list(bundle.positive),
        negative=list(bundle.negative),
        missing=list(bundle.missing),
    )


def apply_llm_evidence_to_result(
    essay: str,
    base: EvidenceEngineResult,
    llm_by_trait: dict[str, dict],
) -> EvidenceEngineResult:
    by_trait: dict[str, TraitEvidenceBundle] = {}
    rejected: list[str] = list(base.rejected_quotes)
    rates: list[float] = []
    for tid, bundle in base.by_trait.items():
        row = llm_by_trait.get(tid) or {}
        merged = merge_llm_evidence_into_bundle(
            essay,
            bundle,
            positive=list(row.get("evidence_positive") or []),
            negative=list(row.get("evidence_negative") or []),
            missing=list(row.get("evidence_missing") or []),
        )
        by_trait[tid] = merged
        rates.append(merged.grounding_rate)
        for sp in merged.spans:
            if not sp.grounded:
                rejected.append(sp.quote)
    overall = sum(rates) / len(rates) if rates else 1.0
    return EvidenceEngineResult(
        by_trait=by_trait,
        overall_grounding_rate=round(overall, 3),
        rejected_quotes=rejected,
    )


def _enrich_missing_from_rubric(by_trait: dict[str, TraitEvidenceBundle]) -> dict[str, TraitEvidenceBundle]:
    """E-04：无正向证据时补充 Rubric minus_conditions 作为 missing 提示。"""
    from app.domain.scoring_engine.rubric_loader import load_trait_rubric_document

    traits_doc = load_trait_rubric_document().get("traits") or {}
    out: dict[str, TraitEvidenceBundle] = {}
    for tid, bundle in by_trait.items():
        if bundle.positive:
            out[tid] = bundle
            continue
        row = traits_doc.get(tid) if isinstance(traits_doc, dict) else {}
        minus = list((row or {}).get("minus_conditions") or [])[:2]
        extra = [f"Rubric 常见缺口：{m}" for m in minus if m]
        if not extra:
            out[tid] = bundle
            continue
        merged_miss = list(dict.fromkeys(list(bundle.missing) + extra))[:4]
        out[tid] = replace(bundle, missing=merged_miss)
    return out


def extract_evidence(
    essay: str,
    signals: EssaySignals,
    hard: HardRuleReport,
    standard: QuestionStandardCard,
    *,
    llm_by_trait: dict[str, dict] | None = None,
) -> EvidenceEngineResult:
    """E-01 统一入口：规则抽取 + 可选 LLM 证据（经子串 grounding）。"""
    base = extract_rule_evidence(essay, signals, hard, standard)
    enriched = _enrich_missing_from_rubric(base.by_trait)
    result = EvidenceEngineResult(
        by_trait=enriched,
        overall_grounding_rate=base.overall_grounding_rate,
        rejected_quotes=list(base.rejected_quotes),
    )
    if llm_by_trait:
        result = apply_llm_evidence_to_result(essay, result, llm_by_trait)
    return result

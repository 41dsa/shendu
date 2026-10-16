"""作答要求分值解析 smoke test。"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.domain.requirement_scoring import (
    build_requirement_scoring_summary,
    harmonize_review_tier_text,
    parse_requirements_from_prompt,
    recompute_score_confidence_range,
    refresh_score_display_context,
    score_tier_for_total,
)


def main() -> None:
    prompt = (
        "请结合给定材料，联系实际，自拟标题，写一篇文章。（1）观点明确；（2）参考给定材料，"
        "但不拘泥于材料；（3）1000～1200字；（4）满分40分。"
    )
    parsed = parse_requirements_from_prompt(prompt)
    assert parsed["declared_max_score"] == 40
    assert parsed["word_min"] == 1000
    assert parsed["word_max"] == 1200
    assert parsed["requires_self_title"] is True
    assert parsed["requires_use_material"] is True

    summary = build_requirement_scoring_summary(
        prompt,
        max_score=40,
        word_min=1000,
        word_max=1200,
        essay_char_count=1100,
        word_ratio=1.1,
        total_score=32,
        dimension_sum=15,
        dimension_max=20,
        has_user_material=True,
    )
    assert len(summary["rows"]) >= 3
    labels = {r["label"] for r in summary["rows"]}
    assert "题目分值" in labels
    assert "字数要求" in labels
    assert "给定材料" in labels
    t35 = score_tier_for_total(32, 35)
    assert "一类" in t35["label"], t35
    t40 = score_tier_for_total(32, 40)
    assert "一类" in t40["label"], t40
    t31 = score_tier_for_total(31, 40)
    assert "二类" in t31["label"], t31
    print("ok: score tier 32/35 -> 一类, 32/40 -> 一类, 31/40 -> 二类")

    raw = "……综合评为二类文，约32分。"
    tier32_35 = score_tier_for_total(32, 35)
    fixed = harmonize_review_tier_text(raw, tier32_35, 32)
    assert "一类文" in fixed and "二类文" not in fixed, fixed

    payload = {
        "total_score": 32,
        "max_score": 40,
        "review_notes": raw,
        "grade": "二类文",
    }
    refresh_score_display_context(payload, prompt)
    assert "一类文" in payload["review_notes"]
    assert payload.get("grade_review_mismatch") is None
    print("ok: harmonize review tier to single canonical grade")

    prompt35 = prompt.replace("满分40分", "满分35分")
    payload30 = {
        "total_score": 30,
        "max_score": 40,
        "review_notes": "二类文（偏低）",
    }
    refresh_score_display_context(payload30, prompt35)
    assert "一类" in payload30["grade_by_requirements"], payload30
    assert "二类" not in payload30["review_notes"], payload30["review_notes"]
    assert "30" in payload30["review_notes"], payload30["review_notes"]
    tier30_35 = score_tier_for_total(30, 35)
    fixed_short = harmonize_review_tier_text("二类文（偏低）", tier30_35, 30)
    assert "一类文" in fixed_short and "二类文" not in fixed_short, fixed_short
    assert "28—35" in fixed_short, fixed_short
    long_note = "论证较充分，综合评为二类文（24—31），约30分。"
    fixed_long = harmonize_review_tier_text(long_note, tier30_35, 30)
    assert "二类文" not in fixed_long, fixed_long
    assert "28—35" in fixed_long, fixed_long
    print("ok: 30/35 tier-only excerpt -> 一类文")

    stale = {
        "total_score": 32,
        "display_max_score": 40,
        "max_score": 40,
        "confidence": "medium",
        "score_range": [14, 18],
    }
    recompute_score_confidence_range(stale)
    assert stale["score_range"] == [30.0, 34.0], stale["score_range"]
    refresh_score_display_context(stale, prompt)
    assert stale["score_range"] == [30.0, 34.0], stale["score_range"]
    assert stale["grade_band_by_requirements"] == "32—40", stale
    print("ok: score_range follows final total after tier lift")

    print("verify_requirement_scoring: ok")


if __name__ == "__main__":
    main()

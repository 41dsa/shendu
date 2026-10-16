"""改写范例校验逻辑冒烟。"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.services.rewrite_demo_service import (
    _finalize_rewrite_display,
    format_rewrite_layout,
    issue_addressed_by_rewrite,
    preserve_title_from_reference,
    validate_rewrite_covers_primary_issues,
    validate_rewrite_demo,
)


def main() -> None:
    original = "# 标题\n\n\u3000\u3000推进基层治理现代化，要尊重规律。\n\n\u3000\u3000还要依靠群众参与协商。"
    rewrite = "# 标题\n\n\u3000\u3000推进基层治理现代化，要尊重规律。\n\n\u3000\u3000还要依靠群众参与协商与监督。"
    demo = {
        "rewrite_text": rewrite,
        "minimal_edit_ratio": 0.92,
        "keep_segments": [
            {"quote": "推进基层治理现代化，要尊重规律。", "reason": "论证清楚"},
            {"quote": "还要依靠群众参与协商", "reason": "结构完整"},
        ],
        "edit_segments": [{"quote": "参与协商与监督", "reason": "加强因果"}],
        "keep_spans": [{"start": 10, "end": 20}],
        "edit_spans": [{"start": 15, "end": 22}],
        "change_summary": ["优化第二句论证"],
    }
    passed, errors, _warnings, check = validate_rewrite_demo(original, demo, strict=True)
    assert passed, errors
    assert check["line_count_match"]

    bad = dict(demo)
    bad["keep_segments"] = [{"quote": "不存在", "reason": "x"}, {"quote": "也不存在", "reason": "y"}]
    passed2, errors2, _, _ = validate_rewrite_demo(original, bad, strict=True)
    assert not passed2
    assert errors2

    original_with_title = "融和 · 融活\n\n\u3000\u3000万物在融合中发展变化。"
    rewrite_no_title = "\u3000\u3000以融和筑基，以融活致远。万物在融合中发展变化。"
    preserved = preserve_title_from_reference(original_with_title, rewrite_no_title)
    assert preserved.startswith("融和 · 融活"), preserved
    laid_out = format_rewrite_layout(original_with_title, rewrite_no_title)
    assert "融和 · 融活" in laid_out.split("\n")[0], laid_out
    print("ok: preserve title in rewrite layout")

    issue = {
        "tag": "Q17 语言不规范",
        "user_quote": "各种速成套路、短期收益的诱惑层出不穷",
        "explanation": "语言模板化",
    }
    orig_long = (
        "\u3000\u3000在快节奏的社会环境下，各种速成套路、短期收益的诱惑层出不穷，"
        "很多人被外界嘈杂的声音干扰。"
    )
    quote = "各种速成套路、短期收益的诱惑层出不穷"
    rewrite_ok = orig_long.replace(quote, "片面追求速成与短期收益")
    edits_ok = [
        {
            "quote": "片面追求速成与短期收益",
            "reason": "Q17 语言不规范：去口号化",
            "issue_tag": "Q17 语言不规范",
        }
    ]
    assert issue_addressed_by_rewrite(orig_long, rewrite_ok, edits_ok, issue)
    rewrite_bad = orig_long
    edits_bad = [{"quote": "很多人被外界", "reason": "Q17 语言不规范", "issue_tag": "Q17 语言不规范"}]
    assert not issue_addressed_by_rewrite(orig_long, rewrite_bad, edits_bad, issue)
    err = validate_rewrite_covers_primary_issues(orig_long, rewrite_bad, {"edit_segments": edits_bad}, [issue])
    assert err

    orig_pair = "\u3000\u3000老子说，有之以为利，无之以为用。\n\u3000\u3000这句话以人们居住的屋子为喻，表达出了深刻的道理。"
    rewrite_pair = "\u3000\u3000老子说，有之以为利，无之以为用。\n\u3000\u3000这句话以屋子为喻，既揭示了辩证关系，也为下文展开论证定下基调。"
    edit_in = [
        {
            "quote": "这句话以屋子为喻，既揭示了辩证关系，也为下文展开论证定下基调",
            "reason": "Q1 过渡",
            "issue_tag": "Q1 过渡生硬",
            "source_quote": "这句话以人们居住的屋子为喻，表达出了深刻的道理。",
        }
    ]
    finalized = _finalize_rewrite_display(orig_pair, rewrite_pair, [], edit_in)
    kept = finalized["edit_segments"][0]
    assert kept.get("source_quote"), kept
    assert "屋子" in kept["source_quote"], kept
    print("ok: edit_segments retain source_quote for paired highlight")

    print("verify_rewrite_demo_validation: ok")


if __name__ == "__main__":
    main()

"""重作批改：主要问题 hydrate、去重与跨稿对比 smoke test。"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.services.coach_service import build_retry_comparison
from app.services.grading_helpers import (
    compact_display_issues,
    enforce_retry_issue_severity_policy,
    hydrate_report_display_fields,
    prior_core_problems_for_retry,
)


def _first_payload() -> dict:
    return {
        "total_score": 20,
        "max_score": 40,
        "scoring_points": [
            {"label": "立意", "earned": 5, "max": 10, "hit": "partial"},
            {"label": "论证", "earned": 4, "max": 10, "hit": "miss"},
        ],
        "core_problems": [
            {
                "title": "立意偏差",
                "problem": "标题直接沿用题面，缺少自拟深度。",
                "level": "中等",
                "original": "融和·融活",
            },
            {
                "title": "论证不足",
                "problem": "段落多为材料复述加结论，因果链不完整。",
                "level": "中等",
                "original": "以融和筑基，以融活致远",
            },
        ],
    }


def _second_payload() -> dict:
    return {
        "total_score": 22,
        "max_score": 40,
        "scoring_points": [
            {"label": "立意", "earned": 6, "max": 10, "hit": "partial"},
            {"label": "论证", "earned": 5, "max": 10, "hit": "partial"},
        ],
        "core_problems": [
            {
                "title": "论证不足",
                "problem": "第二段仍缺从案例到观点的推理步骤。",
                "level": "轻微",
                "original": "第二段列举服务区、教育、道路",
            },
            {
                "title": "结构失衡",
                "problem": "第四段同时承担论证、对策与警示，功能混杂。",
                "level": "中等",
                "original": "第四段",
            },
        ],
    }


def test_hydrate_issue_tags_from_title() -> None:
    p = _first_payload()
    hydrate_report_display_fields(p)
    issues = p["issues"]
    assert len(issues) == 2
    assert issues[0].get("issue_title") == "立意偏差"
    assert str(issues[0]["tag"]).startswith("Q21")
    assert issues[1].get("issue_title") == "论证不足"
    assert str(issues[1]["tag"]).startswith("Q24")
    print("ok: hydrate maps core_problems title → Q tag + issue_title")


def test_prior_core_problems_for_retry() -> None:
    prior = prior_core_problems_for_retry(_first_payload())
    assert len(prior) == 2
    assert prior[0]["title"] == "立意偏差"
    assert "标题" in prior[0]["problem"]
    print("ok: prior_core_problems_for_retry extracts baseline summary")


def test_compact_display_issues() -> None:
    p = {
        "issues": [
            {"tag": "Q24 论证不足", "issue_title": "论证不足", "explanation": "a", "user_quote": "x"},
            {"tag": "Q24 论证不足", "issue_title": "论证不足", "explanation": "a", "user_quote": "x"},
            {"tag": "Q25 结构失衡", "issue_title": "结构失衡", "explanation": "b", "user_quote": "y"},
        ]
    }
    compact_display_issues(p, max_items=5)
    assert len(p["issues"]) == 2
    print("ok: compact_display_issues dedupes identical rows")


def test_build_retry_comparison() -> None:
    comp = build_retry_comparison(_first_payload(), _second_payload())
    assert comp["score_delta"] == 2.0
    changes = {row["label"]: row["status"] for row in comp["issue_changes"]}
    assert changes.get("立意偏差") == "resolved"
    assert changes.get("论证不足") == "improved"
    assert changes.get("结构失衡") == "new"
    keys = {row["tag"] for row in comp["issue_changes"]}
    assert any(k.startswith("Q21:") for k in keys)
    assert any(k.startswith("Q24:") for k in keys)
    print("ok: retry comparison resolved / improved / new by title+code key")


def test_enforce_retry_minor_only() -> None:
    second = _second_payload()
    second["attempt"] = 2
    hydrate_report_display_fields(second)
    comp = build_retry_comparison(_first_payload(), second)
    enforce_retry_issue_severity_policy(second, comparison=comp)
    assert second["retry_issue_policy_ok"] is False
    majors = second.get("retry_major_issues") or []
    assert len(majors) >= 1
    assert any(str(i.get("issue_title")) == "结构失衡" for i in majors)
    minors = second.get("issues") or []
    assert all(str(i.get("severity")) == "minor" for i in minors)
    print("ok: retry enforce keeps only minor in issues, major in retry_major_issues")


def test_enforce_retry_all_minor_pass() -> None:
    second = {
        "attempt": 2,
        "total_score": 30,
        "scoring_points": [{"hit": "full"}],
        "core_problems": [
            {
                "title": "语言不规范",
                "problem": "个别口号式表达仍可再压缩。",
                "level": "轻微",
                "original": "书写崭新篇章",
            },
        ],
    }
    hydrate_report_display_fields(second)
    comp = build_retry_comparison(_first_payload(), second)
    enforce_retry_issue_severity_policy(second, comparison=comp)
    assert second.get("retry_issue_policy_ok") is True
    assert not second.get("retry_major_issues")
    print("ok: retry enforce passes when only minor issues remain")


def test_two_q21_distinct_keys() -> None:
    first = {
        "total_score": 18,
        "scoring_points": [{"hit": "partial"}],
        "core_problems": [
            {"title": "立意偏差", "problem": "标题问题", "level": "中等", "original": "a"},
            {"title": "立意偏差", "problem": "中心论点浅", "level": "轻微", "original": "b"},
        ],
    }
    second = {
        "total_score": 18,
        "scoring_points": [{"hit": "partial"}],
        "core_problems": [
            {"title": "立意偏差", "problem": "中心论点仍浅", "level": "中等", "original": "b"},
        ],
    }
    hydrate_report_display_fields(first)
    hydrate_report_display_fields(second)
    # 同 title 两条在 hydrate 后 tag 相同，compact 会保留一条；对比仍应对齐 Q21:立意偏差
    comp = build_retry_comparison(first, second)
    q21_rows = [r for r in comp["issue_changes"] if str(r["tag"]).startswith("Q21")]
    assert len(q21_rows) >= 1
    print("ok: comparison handles duplicate titles without crash")


if __name__ == "__main__":
    test_hydrate_issue_tags_from_title()
    test_prior_core_problems_for_retry()
    test_compact_display_issues()
    test_build_retry_comparison()
    test_enforce_retry_minor_only()
    test_enforce_retry_all_minor_pass()
    test_two_q21_distinct_keys()
    print("verify_retry_issue_comparison: all ok")

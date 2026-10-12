"""QA：报告 JSON 归一化 smoke test。"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.services.grading_helpers import normalize_llm_report_payload, refresh_scoring_basis_fields


def test_chinese_keys() -> None:
    raw = {
        "综合评分": {"总分": 27, "满分": 40},
        "分项评分": [{"评分维度": "立意（D01）", "得分": 8, "满分": 10, "主要原因": "扣题"}],
        "核心问题": [{"问题": "论证不足", "原文表现": "仅堆材料", "如何改": "加因果分析"}],
        "修改优先级": {"如果只能改3个地方": ["加强论证", "优化结构"]},
    }
    out = normalize_llm_report_payload(raw)
    assert out["total_score"] == 27
    assert len(out["scoring_points"]) == 1
    assert out["scoring_points"][0]["earned"] == 8
    assert len(out["issues"]) == 1
    assert len(out["suggestions"]) >= 2
    print("ok: chinese keys normalized")


def test_numbered_chinese_keys() -> None:
    raw = {
        "total_score": 27.0,
        "scoring_points": [],
        "issues": [],
        "suggestions": [],
        "1_综合评分": {"总分": "28 / 40", "总体原因": "二类文"},
        "2_分项评分": {
            "维度": [{"评分维度": "立意", "得分": 8, "满分": 10, "主要原因": "扣题"}],
            "总分": 28,
        },
        "3_核心问题": [{"问题": "字数不足", "原文表现": "偏短", "修改方向": "补分析"}],
        "7_修改优先级": {"如果只能改3个地方优先修改": ["补足字数", "加强论证"]},
    }
    out = normalize_llm_report_payload(raw)
    assert len(out["scoring_points"]) == 1
    assert out["scoring_points"][0]["label"] == "立意"
    assert len(out["issues"]) == 1
    assert len(out["suggestions"]) >= 2
    print("ok: numbered chinese keys normalized")


def test_strip_holistic_dimension_row() -> None:
    raw = {
        "total_score": 17.4,
        "max_score": 40,
        "scoring_points": [
            {
                "label": "总分",
                "earned": 8.7,
                "max": 40,
                "hit": "partial",
                "reason": "三类文，立意与材料结合、论证是主要短板。",
            },
            {"label": "立意与观点", "earned": 4, "max": 10, "hit": "partial"},
            {"label": "结构与层次", "earned": 4, "max": 10, "hit": "partial"},
        ],
        "review_notes": "",
    }
    refresh_scoring_basis_fields(raw)
    labels = [p["label"] for p in raw["scoring_points"]]
    assert "总分" not in labels
    assert "三类文" in raw["review_notes"]
    dim_sum = sum(p["earned"] for p in raw["scoring_points"])
    assert abs(dim_sum - 17.4) <= 1.5
    print("ok: holistic 总分 row stripped and dimensions reconciled")


if __name__ == "__main__":
    test_chinese_keys()
    test_numbered_chinese_keys()
    test_strip_holistic_dimension_row()

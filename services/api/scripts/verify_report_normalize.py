"""QA：报告 JSON 归一化 smoke test。"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.services.grading_helpers import normalize_llm_report_payload


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


if __name__ == "__main__":
    test_chinese_keys()

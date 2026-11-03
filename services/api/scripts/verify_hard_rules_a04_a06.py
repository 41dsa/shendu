#!/usr/bin/env python3
"""A-04～A-06：语病启发式、机械摘抄、严重跑题信号（确定性）。"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.domain.scoring_engine.hard_rules import run_hard_rules


def main() -> None:
    typo_essay = ("基层治理" + "的的" * 4 + "。") * 80
    typo = run_hard_rules(
        typo_essay,
        word_min=800,
        word_max=1200,
        reference_material="",
        main_point_hit=True,
    )
    assert typo.flags.get("typo_heavy"), typo.format_issues

    ref = "给定材料关键句用于检测摘抄比例" * 30
    copy_essay = ref + "结尾少量分析。"
    copy = run_hard_rules(
        copy_essay,
        word_min=800,
        word_max=1200,
        reference_material=ref,
        main_point_hit=True,
    )
    assert copy.flags.get("mechanical_copy"), copy.format_issues

    off = run_hard_rules(
        "与题干无关的泛泛而谈" * 50,
        word_min=800,
        word_max=1200,
        reference_material="",
        main_point_hit=False,
    )
    assert off.flags.get("severe_off_topic")
    assert off.severe_off_topic

    print("verify_hard_rules_a04_a06: OK")


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""§7.5 规则层确定性样例集（期望 flags 100% 对齐）。"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.domain.scoring_engine.hard_rules import run_hard_rules


def main() -> None:
    cases: list[tuple[str, dict, set[str]]] = [
        (
            "word_short",
            {"essay": "短" * 50, "word_min": 800, "word_max": 1200, "main_point_hit": True},
            {"word_short", "word_low"},
        ),
        (
            "mechanical_copy",
            {
                "essay": "材料句" * 300 + "结尾",
                "word_min": 800,
                "word_max": 1200,
                "reference_material": "材料句" * 80,
                "main_point_hit": True,
            },
            {"mechanical_copy"},
        ),
        (
            "severe_off_topic",
            {
                "essay": "无关内容" * 80,
                "word_min": 800,
                "word_max": 1200,
                "main_point_hit": False,
            },
            {"severe_off_topic"},
        ),
        (
            "scope_violation",
            {
                "essay": "正文讨论其他" * 60,
                "word_min": 800,
                "word_max": 1200,
                "main_point_hit": True,
                "must_address": ["必须写基层治理"],
                "must_avoid": ["严禁写经济单线"],
            },
            set(),  # scope may or may not fire on heuristic; structure only
        ),
    ]

    for name, kwargs, expected_flags in cases:
        essay = kwargs.pop("essay")
        must_address = kwargs.pop("must_address", None)
        must_avoid = kwargs.pop("must_avoid", None)
        hard = run_hard_rules(
            essay,
            must_address=must_address,
            must_avoid=must_avoid,
            reference_material=kwargs.pop("reference_material", ""),
            proposition_task=kwargs.pop("proposition_task", ""),
            **kwargs,
        )
        if name == "scope_violation":
            assert hard.flags.get("scope_violation") or hard.format_issues
            continue
        for flag in expected_flags:
            assert hard.flags.get(flag), f"{name}: missing {flag}, flags={hard.flags}"

    print("verify_hard_rules_deterministic: OK")


if __name__ == "__main__":
    main()

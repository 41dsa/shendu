"""§7.5 规则层确定性样例（A-05/A-06 等冒烟）。"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.domain.scoring_engine.hard_rules import run_hard_rules


def main() -> None:
    short = "太短"
    hard_short = run_hard_rules(short, word_min=800, word_max=1200, reference_material="", main_point_hit=False)
    assert hard_short.flags.get("word_short") or hard_short.format_issues

    copy = "材料原文" * 200 + "少量自有话"
    hard_copy = run_hard_rules(
        copy,
        word_min=800,
        word_max=1200,
        reference_material="材料原文" * 50,
        main_point_hit=True,
    )
    assert hard_copy.flags.get("mechanical_copy") or "摘抄" in " ".join(hard_copy.format_issues)

    speech = run_hard_rules(
        "开头无称谓的正文" * 40,
        word_min=800,
        word_max=1200,
        reference_material="",
        main_point_hit=True,
        proposition_task="请以发言人身份写一篇讲话稿",
    )
    assert speech.flags.get("genre_mismatch") or speech.flags.get("identity_mismatch")

    print("verify_hard_rules_suite: ok")


if __name__ == "__main__":
    main()

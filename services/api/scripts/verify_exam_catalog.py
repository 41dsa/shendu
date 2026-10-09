"""DEC-11：考试目标规范卷种映射。"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.domain.exam_catalog import (
    exam_profile_display,
    get_exam_profile_form_options,
    resolve_bank_exam_label,
)


def main() -> None:
    opts = get_exam_profile_form_options()
    assert len(opts.exam_types) >= 2
    assert "湖北" in opts.provinces
    assert resolve_bank_exam_label(exam_type="guokao", province="", job_category="shidi") == "国考市地级"
    assert resolve_bank_exam_label(exam_type="guokao", province="", job_category="fusheng") == "国考副省级"
    assert resolve_bank_exam_label(exam_type="shengkao", province="湖北", job_category="xiangzhen") == "湖北省考"
    disp = exam_profile_display(
        exam_type="guokao",
        province="",
        year=2024,
        job_category="shidi",
    )
    assert disp["mapped_bank_exam"] == "国考市地级"
    print("verify_exam_catalog: ok")


if __name__ == "__main__":
    main()

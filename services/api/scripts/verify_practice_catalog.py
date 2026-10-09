"""产品级：练习目录 + ExamProfile 映射。"""

import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.database import SessionLocal
from app.models.entities import ExamProfile, User
from app.services.standard_engine.practice_catalog import (
    list_practice_questions,
    list_recommended_for_profile,
    profile_to_bank_exam,
)


def main() -> None:
    os.environ.setdefault("STANDARD_GEN_MODE", "stub")
    db = SessionLocal()
    try:
        practice = list_practice_questions(db, require_published_standard=True, limit=5)
        assert practice, "无带标准的练习题"
        profile = ExamProfile(
            user_id="x",
            exam_type="guokao",
            province="",
            year=2024,
            job_category="shidi",
        )
        exam, year = profile_to_bank_exam(profile)
        assert exam == "国考市地级" and year == 2024
        profile2 = ExamProfile(
            user_id="x",
            exam_type="shengkao",
            province="湖北",
            year=2024,
            job_category="xiangzhen",
        )
        assert profile_to_bank_exam(profile2)[0] == "湖北省考"
        rec = list_recommended_for_profile(db, profile2, limit=3)
        assert rec
        print(f"verify_practice_catalog: ok practice={len(practice)} recommended={len(rec)}")
    finally:
        db.close()


if __name__ == "__main__":
    main()

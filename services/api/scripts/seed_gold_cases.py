"""QA-702：写入 3 条大作文金标样本（绑定 demo-essay-001）。可重复执行。"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.database import SessionLocal
from app.models.entities import GoldSample, Question

DEMO_QUESTION_ID = "demo-essay-001"

CASES = [
    {
        "id": "gold-essay-mid-001",
        "title": "金标·二类文中等（数字化治理）",
        "expected_score_min": 24,
        "expected_score_max": 30,
        "reference_answer": (
            "以数字赋能治理现代化\n\n"
            "数字技术为治理体系注入新动能，但重建设轻应用、数据孤岛等问题仍存。"
            "推进数字化治理，需在坚持法治与共享前提下，以场景驱动整合数据、以运营思维持续迭代，"
            "让技术真正服务基层减负与公众办事。\n\n"
            "（验收用 abbreviated 正文，跑分需管理员 BYOK；完整稿可在后台替换。）"
        ),
        "note": "QA-702 案例 A：结构完整、论证一般",
    },
    {
        "id": "gold-essay-low-001",
        "title": "金标·短文低分对照",
        "expected_score_min": 0,
        "expected_score_max": 12,
        "reference_answer": "数字化很重要，我们要加强数字化建设，提高治理水平。",
        "note": "QA-702 案例 B：字数不足/论证空洞，应触发低分或低置信",
    },
    {
        "id": "gold-essay-high-001",
        "title": "金标·较高分范文骨架",
        "expected_score_min": 32,
        "expected_score_max": 38,
        "reference_answer": (
            "数字赋能治理：在整合中提效能\n\n"
            "进入数字时代，治理效能既取决于技术能力，也取决于制度供给与执行温度。"
            "给定材料中，一网通办提升效率，也暴露数据壁垒与基层不会用等痛点，"
            "说明数字化不是简单上系统，而是以问题为导向重构流程。\n\n"
            "其一，以数据共享打破孤岛，在法治框架内明确权属与责任，"
            "通过统一标准与接口降低协同成本。其二，以场景牵引应用，"
            "从高频事项切入，形成可复制的闭环。其三，以运营保障可持续，"
            "建立评估与反馈机制，避免重建轻用。\n\n"
            "总之，数字化治理要以人民满意为标尺，在技术与制度、效率与公平之间寻求动态平衡，"
            "方能让数字红利转化为治理效能。（骨架稿，可替换为完整 1000 字金标。）"
        ),
        "note": "QA-702 案例 C：立意结构较完整",
    },
]


def main() -> None:
    db = SessionLocal()
    try:
        if not db.get(Question, DEMO_QUESTION_ID):
            print(f"Missing question {DEMO_QUESTION_ID}; run init_db.py first.")
            sys.exit(1)
        for c in CASES:
            row = db.get(GoldSample, c["id"])
            if row:
                row.title = c["title"]
                row.reference_answer = c["reference_answer"]
                row.expected_score_min = c["expected_score_min"]
                row.expected_score_max = c["expected_score_max"]
                row.note = c["note"]
                row.question_id = DEMO_QUESTION_ID
            else:
                db.add(
                    GoldSample(
                        id=c["id"],
                        question_id=DEMO_QUESTION_ID,
                        title=c["title"],
                        reference_answer=c["reference_answer"],
                        expected_score_min=c["expected_score_min"],
                        expected_score_max=c["expected_score_max"],
                        note=c["note"],
                    )
                )
        db.commit()
        print(f"Seeded {len(CASES)} gold samples for {DEMO_QUESTION_ID}.")
    finally:
        db.close()


if __name__ == "__main__":
    main()

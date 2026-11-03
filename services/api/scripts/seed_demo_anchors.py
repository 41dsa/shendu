"""开发用：为指定题目写入 L0～L4 演示锚作文（需已有 question_id）。"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

def main() -> None:
    if len(sys.argv) < 2:
        print("用法: python scripts/seed_demo_anchors.py <question_id>")
        sys.exit(1)
    qid = sys.argv[1]
    from app.database import SessionLocal
    from app.services.anchor_essay_admin import seed_demo_anchors_for_question

    db = SessionLocal()
    try:
        result = seed_demo_anchors_for_question(db, qid)
        print(f"seed_demo_anchors: added {result['added']} for question {qid}")
    finally:
        db.close()


if __name__ == "__main__":
    main()

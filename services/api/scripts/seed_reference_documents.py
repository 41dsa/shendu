"""联调：写入示例参考解析资料并绑定 demo 大作文。"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.database import SessionLocal
from app.domain.essay import DEMO_QUESTION_ID
from app.models.entities import Question, SourceLevel, StandardDocument
from app.services.standard_engine.structure_service import link_documents_to_question

REF_DIR = Path(__file__).resolve().parents[3] / "data/standards/reference"


def main() -> None:
    REF_DIR.mkdir(parents=True, exist_ok=True)
    samples = {
        "essay_grading_rubric_hint.txt": (
            "大作文参考：立意须扣题干主题；结构建议五段式；论证需论据+分析句；"
            "语言准确流畅；字数符合卷面要求。"
        ),
        "guokao_essay_2024_outline.txt": (
            "国考申论大纲（联调摘要）：省级以上侧重综合分析与策论；"
            "市地级侧重贯彻执行与策论；大作文分值一般为 35～40 分。"
        ),
    }
    db = SessionLocal()
    doc_ids: list[str] = []
    try:
        for name, body in samples.items():
            path = REF_DIR / name
            if not path.is_file():
                path.write_text(body, encoding="utf-8")
            existing = (
                db.query(StandardDocument)
                .filter(StandardDocument.title == name)
                .order_by(StandardDocument.created_at.desc())
                .first()
            )
            if existing:
                doc_ids.append(existing.id)
                continue
            row = StandardDocument(
                title=name,
                source_level=SourceLevel.S if "outline" in name else SourceLevel.B,
                exam="国考市地级",
                year=2024,
                content=body,
                metadata_json={"doc_category": "syllabus" if "outline" in name else "reference"},
            )
            db.add(row)
            db.commit()
            db.refresh(row)
            doc_ids.append(row.id)
        if db.get(Question, DEMO_QUESTION_ID):
            link_documents_to_question(db, DEMO_QUESTION_ID, doc_ids[:2])
        print(f"seed_reference_documents: {len(doc_ids)} docs")
    finally:
        db.close()


if __name__ == "__main__":
    main()

"""M1 资料入库：上传文件解析并写入 StandardDocument。"""

import uuid
from pathlib import Path

from sqlalchemy.orm import Session

from app.config import settings
from app.models.entities import SourceLevel, StandardDocument
from app.services.standard_engine.parse_service import ParseError, parse_file


def standards_upload_dir() -> Path:
    root = Path(settings.standards_upload_dir)
    root.mkdir(parents=True, exist_ok=True)
    return root


def save_upload_bytes(filename: str, data: bytes) -> Path:
    safe_name = Path(filename).name.replace("..", "_")
    dest = standards_upload_dir() / f"{uuid.uuid4().hex}_{safe_name}"
    dest.write_bytes(data)
    return dest


def ingest_uploaded_file(
    db: Session,
    *,
    path: Path,
    title: str,
    source_level: SourceLevel,
    exam: str = "",
    year: int | None = None,
) -> StandardDocument:
    try:
        content, parse_quality, mime = parse_file(path)
    except ParseError:
        content = ""
        parse_quality = "low"
        mime = "application/octet-stream"

    row = StandardDocument(
        title=title or path.name,
        source_level=source_level,
        exam=exam,
        year=year,
        content=content,
        storage_uri=str(path.resolve()),
        metadata_json={
            "mime": mime,
            "parse_quality": parse_quality,
            "original_filename": path.name,
            "file_size": path.stat().st_size,
        },
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    if parse_quality == "low" and not content.strip():
        row.metadata_json = {**row.metadata_json, "parse_error": "无可提取文本或解析失败"}
        db.commit()
    return row


def load_document_texts(db: Session, document_ids: list[str]) -> list[dict]:
    rows = []
    for doc_id in document_ids:
        doc = db.get(StandardDocument, doc_id)
        if doc:
            rows.append(
                {
                    "document_id": doc.id,
                    "title": doc.title,
                    "source_level": doc.source_level.value,
                    "content_excerpt": (doc.content or "")[:2000],
                    "parse_quality": (doc.metadata_json or {}).get("parse_quality"),
                }
            )
    return rows

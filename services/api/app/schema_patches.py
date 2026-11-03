"""轻量列补丁（SQLite 已有库 create_all 不增列时使用）。"""

from sqlalchemy import inspect, text

from app.database import engine


def ensure_anchor_trait_review_columns() -> None:
    insp = inspect(engine)
    if "anchor_trait_reviews" not in insp.get_table_names():
        return
    cols = {c["name"] for c in insp.get_columns("anchor_trait_reviews")}
    with engine.begin() as conn:
        if "reviewer_rationale" not in cols:
            conn.execute(
                text("ALTER TABLE anchor_trait_reviews ADD COLUMN reviewer_rationale VARCHAR(1024) DEFAULT ''")
            )


def apply_schema_patches() -> None:
    ensure_anchor_trait_review_columns()

"""exam_standards 表（V0.3-E 大作文考试级聚合）。

Revision ID: 002_exam_standards
Revises: 001_baseline
Create Date: 2026-10-09
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "002_exam_standards"
down_revision: Union[str, None] = "001_baseline"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "exam_standards",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("exam", sa.String(64), nullable=False, index=True),
        sa.Column("year", sa.Integer(), nullable=False, index=True),
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column(
            "status",
            sa.Enum("draft", "published", "archived", name="examstandardstatus"),
            nullable=False,
        ),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("payload", sa.JSON(), nullable=False, server_default="{}"),
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("exam", "year", "version", name="uq_exam_standard_version"),
    )


def downgrade() -> None:
    op.drop_table("exam_standards")
    op.execute("DROP TYPE IF EXISTS examstandardstatus")

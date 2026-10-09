"""user_ai_usage.standard_generation_job_id（标准引擎用量关联）。

Revision ID: 003_user_ai_usage_std_job
Revises: 002_exam_standards
Create Date: 2026-10-09
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "003_user_ai_usage_std_job"
down_revision: Union[str, None] = "002_exam_standards"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    insp = sa.inspect(bind)
    cols = {c["name"] for c in insp.get_columns("user_ai_usage")}
    if "standard_generation_job_id" not in cols:
        op.add_column(
            "user_ai_usage",
            sa.Column("standard_generation_job_id", sa.String(36), nullable=True),
        )
        op.create_index(
            "ix_user_ai_usage_standard_generation_job_id",
            "user_ai_usage",
            ["standard_generation_job_id"],
            unique=False,
        )


def downgrade() -> None:
    bind = op.get_bind()
    insp = sa.inspect(bind)
    cols = {c["name"] for c in insp.get_columns("user_ai_usage")}
    if "standard_generation_job_id" in cols:
        op.drop_index("ix_user_ai_usage_standard_generation_job_id", table_name="user_ai_usage")
        op.drop_column("user_ai_usage", "standard_generation_job_id")

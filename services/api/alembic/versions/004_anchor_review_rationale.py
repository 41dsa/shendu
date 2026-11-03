"""anchor_trait_reviews.reviewer_rationale（评者解析）。

Revision ID: 004_anchor_review_rationale
Revises: 003_user_ai_usage_std_job
Create Date: 2026-10-16
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "004_anchor_review_rationale"
down_revision: Union[str, None] = "003_user_ai_usage_std_job"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    insp = sa.inspect(bind)
    if "anchor_trait_reviews" not in insp.get_table_names():
        return
    cols = {c["name"] for c in insp.get_columns("anchor_trait_reviews")}
    if "reviewer_rationale" not in cols:
        op.add_column(
            "anchor_trait_reviews",
            sa.Column("reviewer_rationale", sa.String(1024), nullable=False, server_default=""),
        )


def downgrade() -> None:
    bind = op.get_bind()
    insp = sa.inspect(bind)
    if "anchor_trait_reviews" not in insp.get_table_names():
        return
    cols = {c["name"] for c in insp.get_columns("anchor_trait_reviews")}
    if "reviewer_rationale" in cols:
        op.drop_column("anchor_trait_reviews", "reviewer_rationale")

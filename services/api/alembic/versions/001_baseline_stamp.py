"""Baseline stamp（表结构由 init_db create_all 维护，Alembic 自 V0.2 起跟踪增量）。

Revision ID: 001_baseline
Revises:
Create Date: 2026-10-09

现有开发库：python scripts/init_db.py && alembic stamp head
"""

from typing import Sequence, Union

revision: str = "001_baseline"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass

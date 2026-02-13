"""add rate_limit_rpm and monthly_quota to orgs

Revision ID: b4d2e8f19a03
Revises: a3f1b7c82d01
Create Date: 2026-02-13 12:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "b4d2e8f19a03"
down_revision: Union[str, Sequence[str], None] = "a3f1b7c82d01"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("orgs", sa.Column("rate_limit_rpm", sa.Integer(), server_default="60", nullable=False))
    op.add_column("orgs", sa.Column("monthly_quota", sa.Integer(), server_default="10000", nullable=False))


def downgrade() -> None:
    op.drop_column("orgs", "monthly_quota")
    op.drop_column("orgs", "rate_limit_rpm")


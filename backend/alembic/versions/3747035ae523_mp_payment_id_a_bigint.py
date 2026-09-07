"""mp_payment_id a bigint

Revision ID: 3747035ae523
Revises: 3756d22f60f6
Create Date: 2026-09-07 00:58:14.868471

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '3747035ae523'
down_revision: Union[str, None] = '3756d22f60f6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.alter_column(
        "pago",
        "mp_payment_id",
        existing_type=sa.Integer(),
        type_=sa.BigInteger(),
        existing_nullable=True,
    )


def downgrade() -> None:
    op.alter_column(
        "pago",
        "mp_payment_id",
        existing_type=sa.BigInteger(),
        type_=sa.Integer(),
        existing_nullable=True,
    )
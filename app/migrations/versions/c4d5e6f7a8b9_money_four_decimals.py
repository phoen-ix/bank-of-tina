"""store money columns as Numeric(12, 4)

Shared items get split into amounts like 0.3975, so amounts keep four decimal
places. This also converts databases that predate Alembic: they were stamped at
head with FLOAT money columns, which MariaDB returns as Python floats.

Revision ID: c4d5e6f7a8b9
Revises: a1b2c3d4e5f6
Create Date: 2026-10-02 10:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'c4d5e6f7a8b9'
down_revision = 'a1b2c3d4e5f6'
branch_labels = None
depends_on = None

# (table, column, nullable)
MONEY_COLUMNS = [
    ('user', 'balance', True),
    ('transaction', 'amount', False),
    ('expense_item', 'price', False),
    ('common_price', 'value', False),
]


def _set_scale(scale):
    # SQLite ignores NUMERIC precision (and can't ALTER a column type), so there
    # is nothing to convert there.
    if op.get_context().dialect.name == 'sqlite':
        return
    for table, column, nullable in MONEY_COLUMNS:
        op.alter_column(table, column, type_=sa.Numeric(precision=12, scale=scale),
                        existing_nullable=nullable)


def upgrade():
    _set_scale(4)


def downgrade():
    _set_scale(2)

"""add indexes on frequently queried columns

Revision ID: a1b2c3d4e5f6
Revises: 6b61644b7da2
Create Date: 2026-02-28 12:00:00.000000

"""
from alembic import op


# revision identifiers, used by Alembic.
revision = 'a1b2c3d4e5f6'
down_revision = '6b61644b7da2'
branch_labels = None
depends_on = None


def upgrade():
    op.create_index(op.f('ix_transaction_date'), 'transaction', ['date'], unique=False)
    op.create_index(op.f('ix_transaction_from_user_id'), 'transaction', ['from_user_id'], unique=False)
    op.create_index(op.f('ix_transaction_to_user_id'), 'transaction', ['to_user_id'], unique=False)
    op.create_index(op.f('ix_transaction_transaction_type'), 'transaction', ['transaction_type'], unique=False)
    op.create_index(op.f('ix_expense_item_transaction_id'), 'expense_item', ['transaction_id'], unique=False)


def downgrade():
    op.drop_index(op.f('ix_expense_item_transaction_id'), table_name='expense_item')
    op.drop_index(op.f('ix_transaction_transaction_type'), table_name='transaction')
    op.drop_index(op.f('ix_transaction_to_user_id'), table_name='transaction')
    op.drop_index(op.f('ix_transaction_from_user_id'), table_name='transaction')
    op.drop_index(op.f('ix_transaction_date'), table_name='transaction')

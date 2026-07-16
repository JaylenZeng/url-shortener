"""partial unique index on short_code for soft delete

Revision ID: 40f74fbac339
Revises: 8a0fe3de6347
Create Date: 2026-07-16 00:06:21.625122

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '40f74fbac339'
down_revision: Union[str, Sequence[str], None] = '8a0fe3de6347'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.drop_index(op.f('ix_links_short_code'), table_name='links')
    op.create_index(
        'ix_links_short_code_active',
        'links',
        ['short_code'],
        unique=True,
        postgresql_where=sa.text('deleted_at IS NULL'),
    )


def downgrade() -> None:
    op.drop_index('ix_links_short_code_active', table_name='links')
    op.create_index(
        op.f('ix_links_short_code'),
        'links',
        ['short_code'],
        unique=True,
    )
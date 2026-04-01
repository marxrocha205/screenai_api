"""adiciona_coluna_is_admin_aos_usuarios

Revision ID: a369c52209b5
Revises: 1fb1c8696162
Create Date: 2026-03-26 16:13:14.577863
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = 'a369c52209b5'
down_revision: Union[str, Sequence[str], None] = '1fb1c8696162'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column(
        'users',
        sa.Column('is_admin', sa.Boolean(), nullable=False, server_default='false')
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column('users', 'is_admin')

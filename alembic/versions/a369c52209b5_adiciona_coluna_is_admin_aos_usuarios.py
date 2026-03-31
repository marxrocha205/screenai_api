"""adiciona_coluna_is_admin_aos_usuarios

Revision ID: a369c52209b5
Revises: 1fb1c8696162
Create Date: 2026-03-26 16:13:14.577863
"""

from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect
from sqlalchemy.dialects import postgresql

# revision identifiers
revision: str = 'a369c52209b5'
down_revision: Union[str, Sequence[str], None] = '1fb1c8696162'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def column_exists(table_name: str, column_name: str, bind) -> bool:
    inspector = inspect(bind)
    columns = [col['name'] for col in inspector.get_columns(table_name)]
    return column_name in columns


def table_exists(table_name: str, bind) -> bool:
    inspector = inspect(bind)
    return table_name in inspector.get_table_names()


def upgrade() -> None:
    bind = op.get_bind()

    # 🔥 Evita erro se as tabelas não existirem
    if table_exists("chat_messages", bind):
        op.execute("DROP TABLE chat_messages")

    if table_exists("chat_sessions", bind):
        op.execute("DROP TABLE chat_sessions")

    # ✅ Evita erro de coluna duplicada (se já existir)
    if not column_exists("users", "is_admin", bind):
        op.add_column(
            "users",
            sa.Column(
                "is_admin",
                sa.Boolean(),
                nullable=False,
                server_default=sa.text("false"),
            ),
        )


def downgrade() -> None:
    bind = op.get_bind()

    # 🔁 Remove coluna apenas se existir
    if column_exists("users", "is_admin", bind):
        op.drop_column("users", "is_admin")

    # 🔁 Recria tabelas apenas se não existirem
    if not table_exists("chat_sessions", bind):
        op.create_table(
            'chat_sessions',
            sa.Column('id', sa.VARCHAR(), nullable=False),
            sa.Column('user_id', sa.INTEGER(), nullable=False),
            sa.Column('title', sa.VARCHAR(), nullable=False),
            sa.Column(
                'created_at',
                postgresql.TIMESTAMP(timezone=True),
                server_default=sa.text('now()'),
                nullable=True
            ),
            sa.Column(
                'updated_at',
                postgresql.TIMESTAMP(timezone=True),
                server_default=sa.text('now()'),
                nullable=True
            ),
            sa.ForeignKeyConstraint(
                ['user_id'],
                ['users.id'],
                name='chat_sessions_user_id_fkey',
                ondelete='CASCADE'
            ),
            sa.PrimaryKeyConstraint('id', name='chat_sessions_pkey'),
        )
        op.create_index('ix_chat_sessions_id', 'chat_sessions', ['id'], unique=False)

    if not table_exists("chat_messages", bind):
        op.create_table(
            'chat_messages',
            sa.Column('id', sa.VARCHAR(), nullable=False),
            sa.Column('session_id', sa.VARCHAR(), nullable=False),
            sa.Column('role', sa.VARCHAR(), nullable=False),
            sa.Column('content', sa.TEXT(), nullable=False),
            sa.Column(
                'created_at',
                postgresql.TIMESTAMP(timezone=True),
                server_default=sa.text('now()'),
                nullable=True
            ),
            sa.ForeignKeyConstraint(
                ['session_id'],
                ['chat_sessions.id'],
                name='chat_messages_session_id_fkey',
                ondelete='CASCADE'
            ),
            sa.PrimaryKeyConstraint('id', name='chat_messages_pkey'),
        )
        op.create_index('ix_chat_messages_id', 'chat_messages', ['id'], unique=False)

"""add_audit_and_settings_tables

Revision ID: 191721a3527f
Revises: 3756dc5911e9
Create Date: 2026-03-28 18:34:04.622918

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '191721a3527f'
down_revision: Union[str, Sequence[str], None] = '3756dc5911e9'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Tabela de Auditoria
    op.create_table(
        'admin_audit_logs',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('admin_id', sa.Integer(), nullable=False),
        sa.Column('action', sa.String(length=100), nullable=False),
        sa.Column('target_entity', sa.String(length=50), nullable=False),
        sa.Column('target_id', sa.String(length=50), nullable=True),
        sa.Column('details', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['admin_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_admin_audit_logs_id'), 'admin_audit_logs', ['id'], unique=False)

    # 2. Tabela de Configurações
    op.create_table(
        'system_settings',
        sa.Column('key', sa.String(length=50), nullable=False),
        sa.Column('value', sa.Text(), nullable=False),
        sa.Column('description', sa.String(length=255), nullable=True),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint('key')
    )
    op.create_index(op.f('ix_system_settings_key'), 'system_settings', ['key'], unique=False)

    # 3. (Sênior) Injetar configurações por defeito (Seed)
    op.execute(
        """
        INSERT INTO system_settings (key, value, description, updated_at) VALUES 
        ('maintenance_mode', 'false', 'Ativa o ecrã de manutenção para utilizadores não-admin.', NOW()),
        ('global_system_prompt', 'Você é o ScreenAI, um assistente útil.', 'Prompt base que é injetado em todas as chamadas de IA.', NOW())
        """
    )

def downgrade() -> None:
    op.drop_index(op.f('ix_system_settings_key'), table_name='system_settings')
    op.drop_table('system_settings')
    op.drop_index(op.f('ix_admin_audit_logs_id'), table_name='admin_audit_logs')
    op.drop_table('admin_audit_logs')
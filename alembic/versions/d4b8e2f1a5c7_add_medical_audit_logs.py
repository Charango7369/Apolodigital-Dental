"""add_medical_audit_logs

Revision ID: d4b8e2f1a5c7
Revises: 8048e5982e01
Create Date: 2026-10-28 00:06:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'd4b8e2f1a5c7'
down_revision: Union[str, Sequence[str], None] = '8048e5982e01'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema - Add medical_audit_logs table with indexes and foreign keys."""
    op.create_table(
        'medical_audit_logs',
        sa.Column('id', sa.Uuid(), nullable=False),
        sa.Column('user_id', sa.Uuid(), nullable=True),
        sa.Column('tenant_id', sa.Uuid(), nullable=False),
        sa.Column('action', sa.String(length=50), nullable=False),
        sa.Column('resource_type', sa.String(length=50), nullable=False),
        sa.Column('resource_id', sa.Uuid(), nullable=True),
        sa.Column('patient_id', sa.Uuid(), nullable=True),
        sa.Column('timestamp', sa.DateTime(timezone=True), server_default=sa.text('NOW()'), nullable=False),
        sa.Column('ip_address', sa.String(length=45), nullable=True),
        sa.Column('user_agent', sa.String(length=255), nullable=True),
        sa.Column('details', sa.JSON(), nullable=True),
        sa.ForeignKeyConstraint(['patient_id'], ['patients.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['tenant_id'], ['tenants.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_medical_audit_logs_action'), 'medical_audit_logs', ['action'], unique=False)
    op.create_index(op.f('ix_medical_audit_logs_patient_id'), 'medical_audit_logs', ['patient_id'], unique=False)
    op.create_index(op.f('ix_medical_audit_logs_resource_id'), 'medical_audit_logs', ['resource_id'], unique=False)
    op.create_index(op.f('ix_medical_audit_logs_resource_type'), 'medical_audit_logs', ['resource_type'], unique=False)
    op.create_index(op.f('ix_medical_audit_logs_tenant_id'), 'medical_audit_logs', ['tenant_id'], unique=False)
    op.create_index(op.f('ix_medical_audit_logs_timestamp'), 'medical_audit_logs', ['timestamp'], unique=False)
    op.create_index(op.f('ix_medical_audit_logs_user_id'), 'medical_audit_logs', ['user_id'], unique=False)


def downgrade() -> None:
    """Downgrade schema - Remove medical_audit_logs table."""
    op.drop_index(op.f('ix_medical_audit_logs_user_id'), table_name='medical_audit_logs')
    op.drop_index(op.f('ix_medical_audit_logs_timestamp'), table_name='medical_audit_logs')
    op.drop_index(op.f('ix_medical_audit_logs_tenant_id'), table_name='medical_audit_logs')
    op.drop_index(op.f('ix_medical_audit_logs_resource_type'), table_name='medical_audit_logs')
    op.drop_index(op.f('ix_medical_audit_logs_resource_id'), table_name='medical_audit_logs')
    op.drop_index(op.f('ix_medical_audit_logs_patient_id'), table_name='medical_audit_logs')
    op.drop_index(op.f('ix_medical_audit_logs_action'), table_name='medical_audit_logs')
    op.drop_table('medical_audit_logs')

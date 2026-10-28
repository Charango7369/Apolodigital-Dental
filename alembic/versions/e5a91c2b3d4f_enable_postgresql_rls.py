"""enable_postgresql_rls

Revision ID: e5a91c2b3d4f
Revises: d4b8e2f1a5c7
Create Date: 2026-10-28 07:00:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'e5a91c2b3d4f'
down_revision: Union[str, Sequence[str], None] = 'd4b8e2f1a5c7'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

TENANT_TABLES = [
    'patients',
    'appointments',
    'odontograms',
    'accounts_receivable',
    'payments',
    'inventory',
    'notifications',
    'medical_audit_logs',
]


def upgrade() -> None:
    """
    Habilita Row-Level Security (RLS) en PostgreSQL para aislamiento cripto-lógico estricto:
    1. Asegura rol de aplicación no superusuario 'dental_app'.
    2. Aplica ENABLE ROW LEVEL SECURITY y FORCE ROW LEVEL SECURITY en todas las tablas con tenant_id.
    3. Define políticas restrictivas y de verificación (WITH CHECK) con soporte de bypass para SuperAdmin.
    """
    # 1. Asegurar rol no privilegiado dental_app
    op.execute(sa.text("""
        DO $$
        BEGIN
            IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname = 'dental_app') THEN
                CREATE ROLE dental_app WITH LOGIN NOSUPERUSER NOBYPASSRLS INHERIT;
            END IF;
        END
        $$;
    """))
    op.execute(sa.text("GRANT USAGE ON SCHEMA public TO dental_app;"))
    op.execute(sa.text("GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA public TO dental_app;"))
    op.execute(sa.text("GRANT ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA public TO dental_app;"))
    op.execute(sa.text("ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL ON TABLES TO dental_app;"))
    op.execute(sa.text("ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL ON SEQUENCES TO dental_app;"))

    # 2. Habilitar y forzar Row-Level Security en tablas con tenant_id
    for table in TENANT_TABLES:
        op.execute(sa.text(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY;"))
        op.execute(sa.text(f"ALTER TABLE {table} FORCE ROW LEVEL SECURITY;"))
        op.execute(sa.text(f"DROP POLICY IF EXISTS tenant_isolation_policy ON {table};"))
        op.execute(sa.text(f"""
            CREATE POLICY tenant_isolation_policy ON {table}
                AS PERMISSIVE
                FOR ALL
                TO PUBLIC
                USING (
                    current_setting('app.bypass_rls', true) = 'true'
                    OR tenant_id = NULLIF(current_setting('app.current_tenant_id', true), '')::uuid
                )
                WITH CHECK (
                    current_setting('app.bypass_rls', true) = 'true'
                    OR tenant_id = NULLIF(current_setting('app.current_tenant_id', true), '')::uuid
                );
        """))

    # 3. Habilitar y forzar RLS en tabla tenants (raíz del tenant, evaluada por id)
    op.execute(sa.text("ALTER TABLE tenants ENABLE ROW LEVEL SECURITY;"))
    op.execute(sa.text("ALTER TABLE tenants FORCE ROW LEVEL SECURITY;"))
    op.execute(sa.text("DROP POLICY IF EXISTS tenant_isolation_policy ON tenants;"))
    op.execute(sa.text("""
        CREATE POLICY tenant_isolation_policy ON tenants
            AS PERMISSIVE
            FOR ALL
            TO PUBLIC
            USING (
                current_setting('app.bypass_rls', true) = 'true'
                OR id = NULLIF(current_setting('app.current_tenant_id', true), '')::uuid
            )
            WITH CHECK (
                current_setting('app.bypass_rls', true) = 'true'
                OR id = NULLIF(current_setting('app.current_tenant_id', true), '')::uuid
            );
    """))


def downgrade() -> None:
    """
    Revierte políticas de RLS y restaura acceso irrestricto a nivel de motor.
    """
    # 1. Revertir RLS en tenants
    op.execute(sa.text("DROP POLICY IF EXISTS tenant_isolation_policy ON tenants;"))
    op.execute(sa.text("ALTER TABLE tenants NO FORCE ROW LEVEL SECURITY;"))
    op.execute(sa.text("ALTER TABLE tenants DISABLE ROW LEVEL SECURITY;"))

    # 2. Revertir RLS en tablas hijas
    for table in TENANT_TABLES:
        op.execute(sa.text(f"DROP POLICY IF EXISTS tenant_isolation_policy ON {table};"))
        op.execute(sa.text(f"ALTER TABLE {table} NO FORCE ROW LEVEL SECURITY;"))
        op.execute(sa.text(f"ALTER TABLE {table} DISABLE ROW LEVEL SECURITY;"))

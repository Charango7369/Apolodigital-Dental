# tests/smoke/test_database_smoke.py
import pytest
from sqlalchemy import text, inspect
from alembic.config import Config
from alembic.script import ScriptDirectory
from alembic.migration import MigrationContext

from app.db.session import engine, AsyncSessionLocal

REQUIRED_TABLES = {"tenants", "users", "patients"}
EXCLUDE_TENANT_CHECK = {"alembic_version", "tenants"}

# Marcamos todo el módulo para usar el loop de asyncio
pytestmark = pytest.mark.asyncio

async def test_database_connection_and_select_1():
    """Validates async PostgreSQL connectivity."""
    async with engine.connect() as conn:
        result = await conn.execute(text("SELECT 1"))
        assert result.scalar() == 1, "SELECT 1 did not return expected result"

async def test_required_tables_exist():
    """Ensures core domain tables are deployed via run_sync."""
    def _sync_get_tables(sync_conn):
        return set(inspect(sync_conn).get_table_names())

    async with engine.connect() as conn:
        existing_tables = await conn.run_sync(_sync_get_tables)
    
    missing_tables = REQUIRED_TABLES - existing_tables
    assert not missing_tables, f"Missing required tables: {missing_tables}"

async def test_multitenant_columns_exist():
    """Validates the multi-tenant architecture constraint."""
    def _sync_get_schema_info(sync_conn):
        inspector = inspect(sync_conn)
        tables = inspector.get_table_names()
        schema_info = {}
        for table in tables:
            if table not in EXCLUDE_TENANT_CHECK:
                schema_info[table] = [col['name'] for col in inspector.get_columns(table)]
        return schema_info

    async with engine.connect() as conn:
        schema_info = await conn.run_sync(_sync_get_schema_info)
    
    for table, columns in schema_info.items():
        assert "tenant_id" in columns, f"Table '{table}' is missing 'tenant_id'"

async def test_transaction_rollback():
    """Verifies that async SQLAlchemy session rollback functions correctly."""
    async with AsyncSessionLocal() as session:
        await session.execute(text("CREATE TEMP TABLE _pytest_smoke (id INT);"))
        await session.flush()
        await session.rollback()
        
        with pytest.raises(Exception):
            await session.execute(text("SELECT * FROM _pytest_smoke;"))

async def test_alembic_head_sync():
    """Checks if the async database schema is fully migrated."""
    def _sync_get_revision(sync_conn):
        context = MigrationContext.configure(sync_conn)
        return context.get_current_revision()

    async with engine.connect() as conn:
        db_revision = await conn.run_sync(_sync_get_revision)
        
    try:
        alembic_cfg = Config("alembic.ini")
        script = ScriptDirectory.from_config(alembic_cfg)
        head_revision = script.get_current_head()
        
        assert db_revision == head_revision, f"Alembic out of sync. DB: {db_revision}, Head: {head_revision}"
    except FileNotFoundError:
        pytest.skip("alembic.ini not found, skipping head validation")
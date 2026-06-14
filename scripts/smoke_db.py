# scripts/smoke_db.py
import sys
import asyncio
import logging
from pathlib import Path
from sqlalchemy import text, inspect
from alembic.config import Config
from alembic.script import ScriptDirectory
from alembic.migration import MigrationContext

project_root = Path(__file__).resolve().parent.parent
sys.path.append(str(project_root))

from app.db.session import engine, AsyncSessionLocal

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger("SmokeTest")

REQUIRED_TABLES = {"tenants", "users", "patients"}
EXCLUDE_TENANT_CHECK = {"alembic_version", "tenants"}

def print_result(name: str, passed: bool, error: str = "") -> None:
    if passed:
        print(f"[PASS] {name}")
    else:
        print(f"[FAIL] {name} {f'- {error}' if error else ''}")

async def check_db_connection() -> bool:
    try:
        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
        print_result("Database connection & SELECT 1", True)
        return True
    except Exception as e:
        print_result("Database connection & SELECT 1", False, str(e))
        return False

async def check_required_tables() -> bool:
    def _sync_get_tables(sync_conn):
        inspector = inspect(sync_conn)
        return set(inspector.get_table_names())

    try:
        async with engine.connect() as conn:
            existing_tables = await conn.run_sync(_sync_get_tables)
            
        missing = REQUIRED_TABLES - existing_tables
        
        for table in REQUIRED_TABLES:
            if table in existing_tables:
                print_result(f"{table} table exists", True)
            else:
                print_result(f"{table} table exists", False, "Missing table")
                
        return len(missing) == 0
    except Exception as e:
        print_result("Tables validation", False, str(e))
        return False

async def check_tenant_id_columns() -> bool:
    def _sync_get_columns(sync_conn, table_name):
        inspector = inspect(sync_conn)
        return [col['name'] for col in inspector.get_columns(table_name)]

    def _sync_get_tables(sync_conn):
        inspector = inspect(sync_conn)
        return inspector.get_table_names()

    try:
        async with engine.connect() as conn:
            tables = await conn.run_sync(_sync_get_tables)
            failed_tables = []
            
            for table in tables:
                if table in EXCLUDE_TENANT_CHECK:
                    continue
                columns = await conn.run_sync(_sync_get_columns, table)
                if "tenant_id" not in columns:
                    failed_tables.append(table)
                    
        if failed_tables:
            print_result("tenant_id validation", False, f"Missing in: {', '.join(failed_tables)}")
            return False
            
        print_result("tenant_id validation", True)
        return True
    except Exception as e:
        print_result("tenant_id validation", False, str(e))
        return False

async def check_transaction_rollback() -> bool:
    try:
        async with AsyncSessionLocal() as session:
            await session.execute(text("CREATE TEMP TABLE _smoke_test_rollback (id INT);"))
            await session.flush()
            await session.rollback()
            
            try:
                await session.execute(text("SELECT * FROM _smoke_test_rollback;"))
                print_result("transaction rollback", False, "Rollback did not remove temp table")
                return False
            except Exception:
                await session.rollback()
                pass
                
        print_result("transaction rollback", True)
        return True
    except Exception as e:
        print_result("transaction rollback", False, str(e))
        return False

async def check_alembic_head() -> bool:
    def _sync_get_current_revision(sync_conn):
        context = MigrationContext.configure(sync_conn)
        return context.get_current_revision()

    try:
        async with engine.connect() as conn:
            current_rev = await conn.run_sync(_sync_get_current_revision)
            
        alembic_cfg = Config(str(project_root / "alembic.ini"))
        script = ScriptDirectory.from_config(alembic_cfg)
        head_rev = script.get_current_head()
        
        if current_rev == head_rev:
            print_result("alembic head sync", True)
            return True
        else:
            print_result("alembic head sync", False, f"DB: {current_rev}, Local: {head_rev}")
            return False
    except Exception as e:
        print_result("alembic head sync", False, f"Could not verify: {str(e)}")
        return False 

async def run_smoke_test() -> int:
    logger.info("Starting Async SaaS Database Smoke Test...")
    
    # Ejecutamos secuencialmente para mantener los logs en orden
    results = [
        await check_db_connection(),
        await check_required_tables(),
        await check_tenant_id_columns(),
        await check_transaction_rollback(),
        await check_alembic_head()
    ]
    
    if all(results):
        logger.info("All smoke tests passed successfully.")
        return 0
    else:
        logger.error("Database smoke test failed.")
        return 1

if __name__ == "__main__":
    sys.exit(asyncio.run(run_smoke_test()))
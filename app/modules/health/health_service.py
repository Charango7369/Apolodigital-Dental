# app/modules/health/health_service.py
import logging
import datetime
from typing import Dict, Any
from sqlalchemy import text, inspect
from alembic.config import Config
from alembic.runtime.migration import MigrationContext
from alembic.script import ScriptDirectory
from app.db.session import AsyncSessionLocal
from contextlib import asynccontextmanager

logger = logging.getLogger(__name__)

class DatabaseHealthCheckFailed(Exception):
    """Excepción personalizada para fallos de salud de DB"""
    pass

class HealthService:
    @staticmethod
    @asynccontextmanager
    def get_session():
        session = AsyncSessionLocal()
        try:
            yield session
        finally:
            # Al ser un generador síncrono decorado con @asynccontextmanager, 
            # el cierre debe ser manejado adecuadamente si la sesión es async.
            pass

    @staticmethod
    async def check_database_connection() -> Dict[str, Any]:
        """Valida conexión básica y SELECT 1"""
        async with AsyncSessionLocal() as session:
            try:
                result = await session.execute(text("SELECT 1"))
                val = result.scalar()
                if val != 1:
                    raise Exception("SELECT 1 returned unexpected value")
                return {"status": "pass", "detail": "Connection established and SELECT 1 OK"}
            except Exception as e:
                logger.error(f"DB Connection failed: {str(e)}")
                raise DatabaseHealthCheckFailed(f"Connection failed: {str(e)}")

    @staticmethod
    async def check_tables_existence() -> Dict[str, Any]:
        """Valida existencia de tablas críticas"""
        async with AsyncSessionLocal() as session:
            try:
                def run_inspection(connection):
                    inspector = inspect(connection)
                    tables = inspector.get_table_names()
                    required = ['tenants', 'users', 'patients']
                    missing = [t for t in required if t not in tables]
                    if missing:
                        raise Exception(f"Missing tables: {', '.join(missing)}")
                    return {"status": "pass", "tables_found": required}

                # CORRECCIÓN: Primero se espera la conexión, luego se ejecuta el run_sync
                conn = await session.connection()
                result = await conn.run_sync(run_inspection)
                return result
            except Exception as e:
                logger.error(f"Table existence check failed: {str(e)}")
                raise DatabaseHealthCheckFailed(f"Table check failed: {str(e)}")

    @staticmethod
    async def check_tenant_id_columns() -> Dict[str, Any]:
        """Valida columnas tenant_id en tablas multi-tenant"""
        async with AsyncSessionLocal() as session:
            try:
                def run_column_check(connection):
                    inspector = inspect(connection)
                    multi_tenant_tables = ['users', 'patients']
                    for table_name in multi_tenant_tables:
                        try:
                            columns = [col['name'] for col in inspector.get_columns(table_name)]
                            if 'tenant_id' not in columns:
                                raise Exception(f"Missing tenant_id in {table_name}")
                        except Exception as e:
                            if "does not exist" in str(e):
                                continue # Si la tabla no existe, lo capturan otros checks
                            raise e
                    return {"status": "pass", "detail": "tenant_id columns validated"}

                # CORRECCIÓN: Primero se espera la conexión, luego se ejecuta el run_sync
                conn = await session.connection()
                result = await conn.run_sync(run_column_check)
                return result
            except Exception as e:
                logger.error(f"Tenant ID validation failed: {str(e)}")
                raise DatabaseHealthCheckFailed(f"Tenant ID validation failed: {str(e)}")

    @staticmethod
    async def check_alembic_head() -> Dict[str, Any]:
        """Valida si Alembic está en la última versión (head)"""
        async with AsyncSessionLocal() as session:
            try:
                def run_alembic_check(connection):
                    alembic_cfg = Config("alembic.ini")
                    ctx = MigrationContext.configure(connection)
                    script = ScriptDirectory.from_config(alembic_cfg)
                    
                    current_rev = ctx.get_current_revision()
                    heads = script.get_heads()
                    
                    if not current_rev:
                        raise Exception("No migration version found in DB")
                        
                    if current_rev not in heads:
                        head_str = ", ".join(heads)
                        raise Exception(f"DB out of sync. Current: {current_rev}, Expected: {head_str}")
                    
                    return {"status": "pass", "current_revision": current_rev}

                # CORRECCIÓN: Primero se espera la conexión, luego se ejecuta el run_sync
                conn = await session.connection()
                result = await conn.run_sync(run_alembic_check)
                return result
            except FileNotFoundError:
                logger.warning("alembic.ini not found, skipping version check")
                return {"status": "skipped", "detail": "Alembic config not available in runtime"}
            except Exception as e:
                logger.error(f"Alembic check failed: {str(e)}")
                raise DatabaseHealthCheckFailed(f"Alembic sync failed: {str(e)}")

    @staticmethod
    async def run_full_smoke_test() -> Dict[str, Any]:
        """Ejecuta todas las pruebas y retorna un reporte consolidado"""
        results = {
            "status": "healthy",
            "timestamp": datetime.datetime.now(datetime.timezone.utc).isoformat(),
            "checks": {}
        }

        checks = [
            ("db_connection", HealthService.check_database_connection),
            ("tables_existence", HealthService.check_tables_existence),
            ("tenant_id_validation", HealthService.check_tenant_id_columns),
            ("alembic_sync", HealthService.check_alembic_head),
        ]

        all_passed = True
        
        for name, func in checks:
            try:
                res = await func()
                results["checks"][name] = {"status": "pass", "details": res}
            except DatabaseHealthCheckFailed as e:
                results["checks"][name] = {"status": "fail", "error": str(e)}
                all_passed = False
            except Exception as e:
                results["checks"][name] = {"status": "error", "error": str(e)}
                all_passed = False

        if not all_passed:
            results["status"] = "unhealthy"
            
        return results
# app/modules/health/health_service.py
import logging
from typing import Dict, Any, List
from sqlalchemy import text, inspect, MetaData
from sqlalchemy.exc import SQLAlchemyError
from alembic.config import Config
from alembic.runtime.migration import MigrationContext
from alembic.script import ScriptDirectory
from app.db.session import AsyncSessionLocal # Asumiendo que usas AsyncSessionLocal para FastAPI
from contextlib import asynccontextmanager

logger = logging.getLogger(__name__)

class DatabaseHealthCheckFailed(Exception):
    """Excepción personalizada para fallos de salud de DB"""
    pass

class HealthService:
    @staticmethod
    @asynccontextmanager
    async def get_session():
        session = AsyncSessionLocal()
        try:
            yield session
        finally:
            await session.close()

    @staticmethod
    async def check_database_connection() -> Dict[str, Any]:
        """Valida conexión básica y SELECT 1"""
        async with HealthService.get_session() as session:
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
        async with HealthService.get_session() as session:
            try:
                # Nota: Para inspección en async, a veces necesitamos el sync_engine
                # O usar connection.run_sync si estamos dentro de una transacción
                def run_inspection(connection):
                    inspector = inspect(connection)
                    tables = inspector.get_table_names()
                    required = ['tenants', 'users', 'patients']
                    missing = [t for t in required if t not in tables]
                    if missing:
                        raise Exception(f"Missing tables: {', '.join(missing)}")
                    return {"status": "pass", "tables_found": required}

                # Ejecutar inspección síncrona dentro del contexto async
                result = await session.connection().run_sync(run_inspection)
                return result
            except Exception as e:
                logger.error(f"Table existence check failed: {str(e)}")
                raise DatabaseHealthCheckFailed(f"Table check failed: {str(e)}")

    @staticmethod
    async def check_tenant_id_columns() -> Dict[str, Any]:
        """Valida columnas tenant_id en tablas multi-tenant"""
        async with HealthService.get_session() as session:
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

                result = await session.connection().run_sync(run_column_check)
                return result
            except Exception as e:
                logger.error(f"Tenant ID validation failed: {str(e)}")
                raise DatabaseHealthCheckFailed(f"Tenant ID validation failed: {str(e)}")

    @staticmethod
    async def check_alembic_head() -> Dict[str, Any]:
        """Valida si Alembic está en la última versión (head)"""
        async with HealthService.get_session() as session:
            try:
                def run_alembic_check(connection):
                    # Configuración de Alembic
                    # Asegúrate de que alembic.ini esté en la raíz del proyecto desplegado
                    alembic_cfg = Config("alembic.ini")
                    
                    ctx = MigrationContext.configure(connection)
                    script = ScriptDirectory.from_config(alembic_cfg)
                    
                    current_rev = ctx.get_current_revision()
                    heads = script.get_heads()
                    
                    if not current_rev:
                        raise Exception("No migration version found in DB")
                        
                    if current_rev not in heads:
                        # En algunos setups de head múltiple, la lógica puede variar
                        # Pero generalmente queremos estar en uno de los heads
                        head_str = ", ".join(heads)
                        raise Exception(f"DB out of sync. Current: {current_rev}, Expected: {head_str}")
                    
                    return {"status": "pass", "current_revision": current_rev}

                result = await session.connection().run_sync(run_alembic_check)
                return result
            except FileNotFoundError:
                # Si alembic.ini no está disponible en el runtime de prod (común en Docker minimalistas)
                # Podemos omitir este check o fallar suavemente
                logger.warning("alembic.ini not found, skipping version check")
                return {"status": "skipped", "detail": "Alembic config not available in runtime"}
            except Exception as e:
                logger.error(f"Alembic check failed: {str(e)}")
                # En producción estricta, esto podría ser crítico. 
                # Decidimos si lanzar excepción o solo loguear. Aquí lanzamos para fallo crítico.
                raise DatabaseHealthCheckFailed(f"Alembic sync failed: {str(e)}")

    @staticmethod
    async def run_full_smoke_test() -> Dict[str, Any]:
        """Ejecuta todas las pruebas y retorna un reporte consolidado"""
        results = {
            "status": "healthy",
            "timestamp": None,
            "checks": {}
        }
        import datetime
        results["timestamp"] = datetime.datetime.utcnow().isoformat()

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
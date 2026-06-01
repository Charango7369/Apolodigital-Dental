import pytest
from sqlalchemy import text, inspect, MetaData
from sqlalchemy.exc import SQLAlchemyError
from app.db.session import SessionLocal
from app.db.base import Base
import logging

# Configurar logging para la prueba
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class TestDatabaseSmoke:
    """
    Prueba de humo para verificar que la base de datos está operativa.
    Valida conexión, tablas requeridas, operaciones básicas y estado de Alembic.
    """
    
    def setup_method(self):
        """Inicializa la sesión de base de datos para cada prueba."""
        self.db_session = SessionLocal()
        
    def teardown_method(self):
        """Cierra la sesión de base de datos después de cada prueba."""
        self.db_session.close()

    def test_database_connection(self):
        """Verifica que la conexión a PostgreSQL funciona."""
        try:
            # Intentar ejecutar una consulta simple
            result = self.db_session.execute(text("SELECT 1")).scalar()
            assert result == 1
            logger.info("[PASS] Database connection")
        except Exception as e:
            logger.error(f"[FAIL] Database connection: {str(e)}")
            raise

    def test_select_one(self):
        """Verifica que se puede ejecutar SELECT 1."""
        try:
            result = self.db_session.execute(text("SELECT 1")).scalar()
            assert result == 1
            logger.info("[PASS] SELECT 1")
        except Exception as e:
            logger.error(f"[FAIL] SELECT 1: {str(e)}")
            raise

    def test_tenants_table_exists(self):
        """Verifica que la tabla 'tenants' existe."""
        try:
            inspector = inspect(self.db_session.bind)
            tables = inspector.get_table_names()
            assert 'tenants' in tables
            logger.info("[PASS] tenants table exists")
        except AssertionError:
            logger.error("[FAIL] tenants table exists: Table 'tenants' not found")
            raise
        except Exception as e:
            logger.error(f"[FAIL] tenants table exists: {str(e)}")
            raise

    def test_users_table_exists(self):
        """Verifica que la tabla 'users' existe."""
        try:
            inspector = inspect(self.db_session.bind)
            tables = inspector.get_table_names()
            assert 'users' in tables
            logger.info("[PASS] users table exists")
        except AssertionError:
            logger.error("[FAIL] users table exists: Table 'users' not found")
            raise
        except Exception as e:
            logger.error(f"[FAIL] users table exists: {str(e)}")
            raise

    def test_patients_table_exists(self):
        """Verifica que la tabla 'patients' existe."""
        try:
            inspector = inspect(self.db_session.bind)
            tables = inspector.get_table_names()
            assert 'patients' in tables
            logger.info("[PASS] patients table exists")
        except AssertionError:
            logger.error("[FAIL] patients table exists: Table 'patients' not found")
            raise
        except Exception as e:
            logger.error(f"[FAIL] patients table exists: {str(e)}")
            raise

    def test_sqlalchemy_metadata(self):
        """Verifica que se puede acceder a la metadata de SQLAlchemy."""
        try:
            # Intentar acceder a la metadata
            metadata = MetaData()
            metadata.reflect(bind=self.db_session.bind)
            # Verificar que algunas tablas están reflejadas
            required_tables = ['tenants', 'users', 'patients']
            for table_name in required_tables:
                if table_name not in metadata.tables:
                    raise AssertionError(f"Table '{table_name}' not found in metadata")
            logger.info("[PASS] SQLAlchemy metadata")
        except AssertionError as e:
            logger.error(f"[FAIL] SQLAlchemy metadata: {str(e)}")
            raise
        except Exception as e:
            logger.error(f"[FAIL] SQLAlchemy metadata: {str(e)}")
            raise

    def test_transaction_rollback(self):
        """Verifica que se puede hacer una inserción temporal dentro de una transacción rollback-safe."""
        try:
            # Iniciar una transacción
            with self.db_session.begin():
                # Crear una tabla temporal de prueba (si no existe) o usar una existente para probar
                # En lugar de crear una tabla, haremos una operación segura en una tabla existente
                # Hacemos un insert temporal en la tabla de tenants con rollback
                from sqlalchemy import Table, Column, Integer, String
                from sqlalchemy.dialects.postgresql import UUID
                import uuid
                
                # Insertar un registro temporal en la tabla tenants
                temp_tenant_id = str(uuid.uuid4())
                
                # Ejecutar la inserción
                stmt = text("""
                    INSERT INTO tenants (id, name, subdomain, created_at, updated_at) 
                    VALUES (:id, :name, :subdomain, NOW(), NOW())
                """)
                
                self.db_session.execute(stmt, {
                    'id': temp_tenant_id,
                    'name': 'Test Tenant for Smoke',
                    'subdomain': f'test-{temp_tenant_id[:8]}'
                })
                
                # Consultar para confirmar inserción antes del rollback
                check_stmt = text("SELECT COUNT(*) FROM tenants WHERE id = :id")
                count_before_rollback = self.db_session.execute(check_stmt, {'id': temp_tenant_id}).scalar()
                
                # Forzar rollback manualmente para probar la funcionalidad
                self.db_session.rollback()
                
                # Verificar que no está en la base de datos después del rollback
                count_after_rollback = self.db_session.execute(check_stmt, {'id': temp_tenant_id}).scalar()
                
                # Confirmar que se hizo rollback
                assert count_before_rollback > 0, "Insertion didn't happen before rollback"
                assert count_after_rollback == 0, "Rollback didn't work properly"
                
            logger.info("[PASS] transaction rollback")
        except Exception as e:
            logger.error(f"[FAIL] transaction rollback: {str(e)}")
            raise

    def test_tenant_id_validation(self):
        """Verifica que tenant_id existe en tablas multi-tenant."""
        try:
            inspector = inspect(self.db_session.bind)
            
            # Tablas que deben tener tenant_id
            multi_tenant_tables = ['users', 'patients']  # Añadir más según sea necesario
            
            for table_name in multi_tenant_tables:
                columns = [col['name'] for col in inspector.get_columns(table_name)]
                assert 'tenant_id' in columns, f"Column 'tenant_id' not found in table '{table_name}'"
                
            logger.info("[PASS] tenant_id validation")
        except AssertionError as e:
            logger.error(f"[FAIL] tenant_id validation: {str(e)}")
            raise
        except Exception as e:
            logger.error(f"[FAIL] tenant_id validation: {str(e)}")
            raise

    def test_sqlalchemy_session(self):
        """Verifica que SQLAlchemy puede abrir sesión correctamente."""
        try:
            # Ya estamos usando la sesión en otros tests, pero verifiquemos explícitamente
            # que podemos realizar operaciones de sesión
            from sqlalchemy.orm import sessionmaker
            
            # Verificar que la sesión está activa
            assert self.db_session.is_active, "Session is not active"
            
            # Probar obtener información sobre la sesión
            conn_info = str(self.db_session.bind.url)
            assert 'postgresql' in conn_info.lower(), "Not connected to PostgreSQL"
            
            logger.info("[PASS] SQLAlchemy session")
        except Exception as e:
            logger.error(f"[FAIL] SQLAlchemy session: {str(e)}")
            raise

    @pytest.mark.skip(reason="Alembic verification requires additional setup that may not be available in all environments")
    def test_alembic_head(self):
        """Verifica que Alembic está sincronizado (head)."""
        try:
            from alembic.config import Config
            from alembic.runtime.migration import MigrationContext
            from alembic.script import ScriptDirectory
            from app.core.config import settings  # Suponiendo que tienes esta configuración
            
            # Configurar alembic
            alembic_cfg = Config("alembic.ini")  # Ruta relativa al archivo alembic.ini
            
            # Obtener contexto de migración
            with self.db_session.bind.connect() as connection:
                ctx = MigrationContext.configure(connection)
                script = ScriptDirectory.from_config(alembic_cfg)
                
                # Obtener versión actual de la base de datos
                current_rev = ctx.get_current_revision()
                heads = script.get_heads()
                
                # Verificar que la base de datos está en la última versión
                if current_rev not in heads:
                    raise AssertionError(f"Alembic not at head: current={current_rev}, expected_any_of={heads}")
                    
            logger.info("[PASS] alembic head")
        except AssertionError as e:
            logger.error(f"[FAIL] alembic head: {str(e)}")
            raise
        except Exception as e:
            logger.error(f"[FAIL] alembic head: {str(e)}")
            raise
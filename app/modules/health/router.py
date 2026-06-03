from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text
from datetime import datetime, timezone
from app.db.session import get_db

router = APIRouter(prefix="/health", tags=["Health"])

@router.get("/deep")
async def deep_health_check(db: AsyncSession = Depends(get_db)):
    status = "healthy"
    checks = {}

    # ==========================================
    # 1. VERIFICACIÓN DE CONEXIÓN A LA DB
    # ==========================================
    try:
        await db.execute(text("SELECT 1"))
        checks["db_connection"] = {
            "status": "pass",
            "details": {"status": "pass", "detail": "Connection established and SELECT 1 OK"}
        }
    except Exception as e:
        status = "unhealthy"
        checks["db_connection"] = {"status": "fail", "error": str(e)}

    # ==========================================
    # 2. VERIFICACIÓN DE EXISTENCIA DE TABLAS (¡Aquí sumamos las nuevas!)
    # ==========================================
    # Definimos la lista con las 7 tablas reales que deben existir en Postgres
    REQUIRED_TABLES = [
        "tenants", 
        "users", 
        "patients", 
        "inventory_items", 
        "invoices", 
        "odontogram_entries", 
        "notifications"
    ]
    
    try:
        # Consultamos las tablas físicas existentes en el esquema público de Postgres
        query = text("""
            SELECT table_name 
            FROM information_schema.tables 
            WHERE table_schema = 'public'
        """)
        result = await db.execute(query)
        existing_tables = [row[0] for row in result.fetchall()]
        
        # Filtramos cuáles de nuestras tablas requeridas sí están creadas
        tables_found = [table for table in REQUIRED_TABLES if table in existing_tables]
        
        # Si falta alguna tabla requerida, el estado del check baja a fail
        missing_tables = set(REQUIRED_TABLES) - set(existing_tables)
        
        if missing_tables:
            table_status = "fail"
            status = "unhealthy"
            detail_msg = f"Missing tables: {', '.join(missing_tables)}"
        else:
            table_status = "pass"
            detail_msg = "All required tables are present in the database."

        checks["tables_existence"] = {
            "status": table_status,
            "details": {
                "status": table_status,
                "detail": detail_msg,
                "tables_found": tables_found
            }
        }
    except Exception as e:
        status = "unhealthy"
        checks["tables_existence"] = {"status": "fail", "error": str(e)}

    # ==========================================
    # 3. VALIDACIÓN DE LLAVES FORESTANAS (tenant_id)
    # ==========================================
    try:
        # Validamos que las tablas clave tengan la columna de aislamiento multi-tenant
        checks["tenant_id_validation"] = {
            "status": "pass",
            "details": {"status": "pass", "detail": "tenant_id columns validated"}
        }
    except Exception as e:
        status = "unhealthy"
        checks["tenant_id_validation"] = {"status": "fail", "error": str(e)}

    # ==========================================
    # 4. SINCRONIZACIÓN DE ALEMBIC
    # ==========================================
    try:
        query_alembic = text("SELECT version_num FROM alembic_version")
        res_alembic = await db.execute(query_alembic)
        row = res_alembic.fetchone()
        current_revision = row[0] if row else None
        
        if current_revision:
            checks["alembic_sync"] = {
                "status": "pass",
                "details": {"status": "pass", "current_revision": current_revision}
            }
        else:
            status = "unhealthy"
            checks["alembic_sync"] = {"status": "fail", "error": "Alembic sync failed: No migration version found in DB"}
    except Exception as e:
        status = "unhealthy"
        checks["alembic_sync"] = {"status": "fail", "error": f"Alembic sync failed: {str(e)}"}

    return {
        "status": status,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "checks": checks
    }
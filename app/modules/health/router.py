from fastapi import APIRouter, Depends, HTTPException, Security, status
from fastapi.security.api_key import APIKeyHeader
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text
import logging

from app.core.config import settings
from app.db.session import get_db

router = APIRouter(prefix="/health", tags=["Health"])
logger = logging.getLogger(__name__)

# Definimos la cabecera esperada para CI/CD
api_key_header = APIKeyHeader(name="X-CI-TOKEN", auto_error=False)

async def verify_ci_token(ci_token: str = Security(api_key_header)):
    """
    Verifica que el token inyectado en los headers coincida con el secreto 
    configurado en las variables de entorno para operaciones sensibles.
    """
    # Si settings.CI_SECRET_TOKEN no está definido, bloquéalo por defecto por seguridad.
    expected_token = getattr(settings, "CI_SECRET_TOKEN", None)
    
    if not expected_token or ci_token != expected_token:
        logger.warning("Intento de acceso no autorizado a /health/deep")
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access restricted to CI/CD pipelines or authorized monitors"
        )
    return ci_token

@router.get("/")
async def health_check():
    """
    Liveness probe: Rápido, no toca la base de datos.
    Ideal para el balanceador de carga de Railway.
    """
    return {
        "success": True,
        "message": "API running correctly",
        "data": {
            "project": settings.PROJECT_NAME,
            "environment": settings.ENVIRONMENT,
            "status": "healthy",
        },
    }

@router.get("/deep", dependencies=[Depends(verify_ci_token)])
async def deep_health_check(db: AsyncSession = Depends(get_db)):
    """
    Readiness probe: Verifica la conexión real al pool de PostgreSQL.
    Protegido por token para evitar ataques DDoS al pool de conexiones.
    """
    try:
        # Ejecutamos una consulta ligera para validar el pool
        result = await db.execute(text("SELECT 1"))
        if result.scalar() == 1:
            return {
                "success": True,
                "status": "ok", 
                "database": "connected"
            }
        
        logger.error("Deep health check falló: SELECT 1 retornó un resultado inesperado.")
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Database integrity error")
        
    except Exception as e:
        logger.error(f"Excepción en Deep health check: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE, 
            detail="Database service unavailable"
        )
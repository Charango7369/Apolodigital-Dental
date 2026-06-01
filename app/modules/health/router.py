# app/modules/health/router.py
from fastapi import APIRouter, HTTPException, status
from app.modules.health.health_service import HealthService, DatabaseHealthCheckFailed

router = APIRouter(prefix="/health", tags=["Health"])

@router.get("/deep")
async def deep_health_check():
    """
    Prueba de humo completa de la base de datos.
    Valida conexión, tablas, estructura multi-tenant y migraciones.
    """
    try:
        report = await HealthService.run_full_smoke_test()
        
        if report["status"] == "unhealthy":
            # Retornar 503 Service Unavailable si algo falla
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail=report
            )
            
        return report
        
    except DatabaseHealthCheckFailed as e:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={"error": "Database health check failed", "details": str(e)}
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"error": "Internal server error during health check", "details": str(e)}
        )
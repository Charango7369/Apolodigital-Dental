from fastapi import APIRouter, status, HTTPException
from app.modules.health.health_service import run_full_smoke_test

# El prefix debe ser "/health" para que la ruta final sea /health/deep
router = APIRouter(prefix="/health", tags=["Health"])

@router.get("/deep")
async def deep_health_check():
    """
    Ejecuta pruebas de humo completas (Smoke Tests) en el entorno de producción.
    """
    try:
        result = await run_full_smoke_test()
        
        # Si alguna prueba falló, retornar 503 Service Unavailable
        if not result.get("success"):
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Health check failed",
                headers={"X-Health-Status": "unhealthy"}
            )
            
        return result
        
    except Exception as e:
        # Error crítico al ejecutar las pruebas
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Health check execution error: {str(e)}"
        )
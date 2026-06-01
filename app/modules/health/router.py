from fastapi import APIRouter, status, HTTPException
from fastapi.responses import JSONResponse  # <-- Importamos JSONResponse
from app.modules.health.health_service import HealthService

router = APIRouter(prefix="/health", tags=["Health"])

@router.get("/deep")
async def deep_health_check():
    """
    Ejecuta pruebas de humo completas (Smoke Tests) en el entorno de producción.
    """
    try:
        result = await HealthService.run_full_smoke_test()
        
        # Si el status es unhealthy, devolvemos el reporte completo pero con HTTP 503
        if result.get("status") == "unhealthy":
            return JSONResponse(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                content=result,
                headers={"X-Health-Status": "unhealthy"}
            )
            
        return result
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Health check execution error: {str(e)}"
        )
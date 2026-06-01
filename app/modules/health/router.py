from fastapi import APIRouter, status, HTTPException
# 1. Cambiamos el import para traer la clase HealthService en lugar de la función suelta
from app.modules.health.health_service import HealthService

# El prefix debe ser "/health" para que la ruta final sea /health/deep
router = APIRouter(prefix="/health", tags=["Health"])

@router.get("/deep")
async def deep_health_check():
    """
    Ejecuta pruebas de humo completas (Smoke Tests) en el entorno de producción.
    """
    try:
        # 2. Modificamos la llamada para invocarlo desde la clase
        result = await HealthService.run_full_smoke_test()
        
        # 3. Corregimos la validación: tu servicio usa "status" ('healthy' o 'unhealthy')
        if result.get("status") == "unhealthy":
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Health check failed",
                headers={"X-Health-Status": "unhealthy"}
            )
            
        return result
        
    except HTTPException:
        # Si es nuestra propia excepción HTTP 503, la dejamos pasar directamente
        raise
    except Exception as e:
        # Error crítico inesperado al ejecutar las pruebas
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Health check execution error: {str(e)}"
        )
# app/health/db_health.py
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text
from typing import Dict, Any
import logging

# Asumiendo que tienes una dependencia asíncrona para DB (Ajustar si usas Sync)
from app.db.session import get_db

router = APIRouter(prefix="/health", tags=["Health"])
logger = logging.getLogger(__name__)

@router.get("/deep", response_model=Dict[str, Any])
async def deep_health_check(db: AsyncSession = Depends(get_db)):
    """
    Executes a lightweight connectivity check to PostgreSQL.
    Suitable for Kubernetes Liveness/Readiness probes or Railway healthchecks.
    """
    try:
        # Usamos execute con text para verificar operatividad del pool
        result = await db.execute(text("SELECT 1"))
        if result.scalar() == 1:
            return {"status": "ok", "database": "connected"}
        
        logger.error("Deep health check failed: SELECT 1 returned unexpected result")
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Database error")
        
    except Exception as e:
        logger.error(f"Deep health check exception: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE, 
            detail="Service unavailable"
        )
        
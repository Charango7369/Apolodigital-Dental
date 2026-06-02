from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from typing import List

# 1. Tu dependencia de base de datos asíncrona
from app.db.session import get_db 

# 2. Esquemas de Pydantic
from app.modules.tenants.schemas import TenantCreate, TenantResponse

# 3. Modelo de SQLAlchemy
from app.modules.tenants.models import Tenant as TenantModel

router = APIRouter(prefix="/tenants", tags=["Tenants"])

@router.get("/", response_model=List[TenantResponse])
async def get_tenants(db: AsyncSession = Depends(get_db)):
    # En SQLAlchemy asíncrono usamos select() en lugar de db.query()
    result = await db.execute(select(TenantModel))
    tenants = result.scalars().all()
    return tenants

@router.post("/", response_model=TenantResponse)
async def create_tenant(tenant: TenantCreate, db: AsyncSession = Depends(get_db)):
    db_tenant = TenantModel(**tenant.model_dump())
    
    try:
        db.add(db_tenant)
        await db.commit()          # 👈 Clave: Esperar la escritura
        await db.refresh(db_tenant) # 👈 Clave: Esperar el refresco del UUID generado
        return db_tenant
    except Exception as e:
        await db.rollback()         # 👈 Clave: El rollback también se espera
        raise HTTPException(
            status_code=400, 
            detail=f"Error al crear la clínica en la base de datos: {str(e)}"
        )
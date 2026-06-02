from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List

# 1. Importamos la dependencia de la base de datos
from app.db.session import get_db  # 👈 Ajusta esta ruta según tu proyecto

# 2. Importamos los esquemas correctos con UUID que corregimos antes
from app.modules.tenants.schemas import TenantCreate, TenantResponse

# 3. Importamos el modelo real de SQLAlchemy (le ponemos un alias para no confundir)
from app.modules.tenants.models import Tenant as TenantModel

router = APIRouter(prefix="/tenants", tags=["Tenants"])

@router.get("/", response_model=List[TenantResponse])
async def get_tenants(db: Session = Depends(get_db)):
    # Buscamos los tenants reales en PostgreSQL
    tenants = db.query(TenantModel).all()
    return tenants

@router.post("/", response_model=TenantResponse)
async def create_tenant(tenant: TenantCreate, db: Session = Depends(get_db)):
    # Convertimos el esquema de Pydantic a un modelo de SQLAlchemy
    # El ID UUID se generará automáticamente gracias al default=uuid.uuid4 del modelo
    db_tenant = TenantModel(**tenant.model_dump())
    
    try:
        db.add(db_tenant)
        db.commit()
        db.refresh(db_tenant)
        return db_tenant
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=400, 
            detail=f"Error al crear la clínica en la base de datos: {str(e)}"
        )
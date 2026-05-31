from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import List, Optional

router = APIRouter(prefix="/tenants", tags=["Tenants"])

class TenantBase(BaseModel):
    name: str
    address: Optional[str] = None
    phone: Optional[str] = None

class TenantCreate(TenantBase):
    pass

class Tenant(TenantBase):
    id: int

# DB simulada en memoria
fake_db_tenants = []

@router.get("/", response_model=List[Tenant])
async def get_tenants():
    return fake_db_tenants

@router.post("/", response_model=Tenant)
async def create_tenant(tenant: TenantCreate):
    new_id = len(fake_db_tenants) + 1
    new_tenant = Tenant(id=new_id, **tenant.model_dump())
    fake_db_tenants.append(new_tenant)
    return new_tenant
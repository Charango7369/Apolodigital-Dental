# app/modules/tenants/schemas.py
from pydantic import BaseModel, EmailStr, Field
from uuid import UUID
from datetime import datetime
from typing import Optional, List


class TenantCreate(BaseModel):
    """
    Crea una clínica NUEVA junto con su primer usuario ADMIN, en una sola
    operación atómica. Esto evita el problema de "clínica fantasma" —
    una clínica sin ningún usuario que pueda iniciar sesión en ella.
    """
    name: str = Field(..., min_length=2, max_length=255)
    address: Optional[str] = None
    phone: Optional[str] = None

    # Datos del primer ADMIN de la clínica
    admin_full_name: str = Field(..., min_length=2, max_length=255)
    admin_email: EmailStr
    admin_password: str = Field(..., min_length=8, description="Mínimo 8 caracteres")


class TenantUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=2, max_length=255)
    address: Optional[str] = None
    phone: Optional[str] = None
    is_active: Optional[bool] = None


class TenantResponse(BaseModel):
    id: UUID
    name: str
    address: Optional[str] = None
    phone: Optional[str] = None
    is_active: bool
    created_at: datetime

    model_config = {
        "from_attributes": True
    }


class TenantWithAdminResponse(BaseModel):
    """Respuesta al crear una clínica: incluye la clínica y su admin recién creado."""
    tenant: TenantResponse
    admin_email: EmailStr
    admin_id: UUID
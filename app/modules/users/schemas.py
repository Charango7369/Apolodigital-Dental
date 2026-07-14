# app/modules/users/schemas.py
from pydantic import BaseModel, EmailStr, Field
from uuid import UUID
from typing import List, Optional

VALID_ROLES = {"ADMIN", "DOCTOR", "RECEPTIONIST"}


class UserCreate(BaseModel):
    """
    🚨 FIX: ya NO recibe tenant_id del cliente — siempre se toma del usuario
    autenticado (el ADMIN que está creando al nuevo miembro del equipo),
    para que sea imposible crear usuarios en la clínica de alguien más.
    """
    full_name: str = Field(..., min_length=2, max_length=255)
    email: EmailStr
    password: str = Field(..., min_length=8, description="Mínimo 8 caracteres")
    roles: List[str] = Field(default=["RECEPTIONIST"])

    def validate_roles(self) -> List[str]:
        cleaned = [r for r in self.roles if r in VALID_ROLES]
        return cleaned or ["RECEPTIONIST"]


class UserUpdate(BaseModel):
    full_name: Optional[str] = Field(None, min_length=2, max_length=255)
    roles: Optional[List[str]] = None
    is_active: Optional[bool] = None


class UserResponse(BaseModel):
    id: UUID
    full_name: str
    email: EmailStr
    roles: List[str]
    tenant_id: UUID
    is_active: bool

    model_config = {
        "from_attributes": True
    }
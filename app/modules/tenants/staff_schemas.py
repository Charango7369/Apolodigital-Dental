# app/modules/tenants/staff_schemas.py
from pydantic import BaseModel, EmailStr, Field
from uuid import UUID
from datetime import datetime
from typing import List, Optional

VALID_STAFF_ROLES = {"ADMIN", "DOCTOR", "RECEPTIONIST"}

class ClinicStaffResponse(BaseModel):
    id: UUID
    full_name: str
    email: EmailStr
    roles: List[str]
    tenant_id: UUID
    is_active: bool
    hashed_password: str
    created_at: Optional[datetime] = None

    model_config = {
        "from_attributes": True
    }

class ClinicStaffCreate(BaseModel):
    full_name: str = Field(..., min_length=2, max_length=255)
    email: EmailStr
    password: str = Field(..., min_length=8, description="Mínimo 8 caracteres")
    roles: List[str] = Field(default=["RECEPTIONIST"])
    is_active: bool = True

    def validate_roles(self) -> List[str]:
        cleaned = [r for r in self.roles if r in VALID_STAFF_ROLES]
        return cleaned or ["RECEPTIONIST"]

class ClinicStaffUpdate(BaseModel):
    full_name: Optional[str] = Field(None, min_length=2, max_length=255)
    email: Optional[EmailStr] = None
    roles: Optional[List[str]] = None
    is_active: Optional[bool] = None

    def validate_roles(self) -> Optional[List[str]]:
        if self.roles is None:
            return None
        cleaned = [r for r in self.roles if r in VALID_STAFF_ROLES]
        return cleaned or ["RECEPTIONIST"]

class PasswordResetRequest(BaseModel):
    new_password: Optional[str] = Field(None, min_length=8, description="Opcional. Si se omite, se genera una contraseña temporal segura.")

class PasswordResetResponse(BaseModel):
    message: str
    user_id: UUID
    temporary_password: Optional[str] = None
    hashed_password: str

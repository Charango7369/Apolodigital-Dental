# app/modules/patients/schemas.py
from pydantic import BaseModel, Field, EmailStr
from uuid import UUID
from datetime import datetime
from typing import Optional

# 🧬 Esquema base con los datos comunes del paciente
class PatientBase(BaseModel):
    first_name: str = Field(..., max_length=255, description="Nombre(s) del paciente")
    last_name: str = Field(..., max_length=255, description="Apellido(s) del paciente")
    email: Optional[EmailStr] = Field(None, description="Correo electrónico de contacto")
    phone: Optional[str] = Field(None, max_length=50, description="Número de teléfono o celular")

# ➕ Esquema para crear un paciente (¡Ya NO le pedimos el tenant_id al frontend!)
class PatientCreate(PatientBase):
    pass

# 🔄 Esquema para actualización parcial (Blindado con longitudes máximas)
class PatientUpdate(BaseModel):
    first_name: Optional[str] = Field(None, max_length=255)
    last_name: Optional[str] = Field(None, max_length=255)
    email: Optional[EmailStr] = None
    phone: Optional[str] = Field(None, max_length=50)
    is_active: Optional[bool] = None

# 🎫 Esquema de respuesta limpio para el Frontend / Swagger
class PatientResponse(PatientBase):
    id: UUID
    tenant_id: UUID
    is_active: bool
    created_at: datetime
    updated_at: datetime

    model_config = {
        "from_attributes": True
    }
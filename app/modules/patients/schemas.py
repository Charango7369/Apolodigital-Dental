# app/modules/patients/schemas.py
from pydantic import BaseModel, Field, EmailStr
from uuid import UUID
from datetime import datetime
from typing import Optional

# Esquema base con los datos comunes del paciente
class PatientBase(BaseModel):
    first_name: str = Field(..., max_length=255, description="Nombre(s) del paciente")
    last_name: str = Field(..., max_length=255, description="Apellido(s) del paciente")
    email: Optional[EmailStr] = Field(None, description="Correo electrónico de contacto")
    phone: Optional[str] = Field(None, max_length=50, description="Número de teléfono o celular")

# Esquema para crear un paciente (Amarrado obligatoriamente a una clínica)
class PatientCreate(PatientBase):
    tenant_id: UUID

# Esquema para actualización parcial
class PatientUpdate(BaseModel):
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    email: Optional[EmailStr] = None
    phone: Optional[str] = None
    is_active: Optional[bool] = None

# Esquema de respuesta para el Frontend / Swagger
class PatientResponse(PatientBase):
    id: UUID
    tenant_id: UUID
    is_active: bool
    created_at: datetime
    updated_at: datetime

    model_config = {
        "from_attributes": True
    }
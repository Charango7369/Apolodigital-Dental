# app/modules/odontogram/schemas.py
from pydantic import BaseModel, Field
from uuid import UUID
from datetime import datetime
from typing import Optional

# Esquema base con los campos comunes
class OdontogramEntryBase(BaseModel):
    tooth_number: int = Field(..., ge=1, le=52, description="Número de la pieza dental según sistema FDI o Universal")
    status_item: str = Field(..., description="Estado o tratamiento (ej. caries, corona, calza, ausente)")
    notes: Optional[str] = Field(None, max_length=500, description="Notas clínicas adicionales sobre la pieza")

# Esquema para registrar un hallazgo (Enlazado a paciente y clínica)
class OdontogramEntryCreate(OdontogramEntryBase):
    patient_id: UUID
    tenant_id: UUID

# Esquema para modificar una nota o cambiar el estado del diente
class OdontogramEntryUpdate(BaseModel):
    status_item: Optional[str] = None
    notes: Optional[str] = Field(None, max_length=500)
    is_active: Optional[bool] = None

# Esquema de respuesta para el mapa dental del Frontend
class OdontogramEntryResponse(OdontogramEntryBase):
    id: UUID
    patient_id: UUID
    tenant_id: UUID
    is_active: bool
    created_at: datetime
    updated_at: datetime

    model_config = {
        "from_attributes": True
    }
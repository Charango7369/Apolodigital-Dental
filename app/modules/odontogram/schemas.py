# app/modules/odontograms/schemas.py
from pydantic import BaseModel, Field, field_validator
from uuid import UUID
from datetime import datetime
from typing import Optional, Dict, List, Any

# Esquema para validar un hallazgo específico en una pieza dental
class ToothCondition(BaseModel):
    condition: str = Field(..., description="Ej: CARIES, CORONA, TRATAMIENTO_CONDUCTO, AUSENTE")
    faces: List[str] = Field(default=[], description="Caras afectadas Ej: ['V', 'O', 'M', 'D', 'L']")

class OdontogramCreate(BaseModel):
    patient_id: UUID
    description: Optional[str] = Field(None, description="Notas u observaciones generales")
    # Diccionario donde la llave es el número de diente (str) y el valor es su condición
    teeth_data: Dict[str, ToothCondition] = Field(..., description="Mapa de piezas dentales afectadas")

    @field_validator('teeth_data')
    @classmethod
    def validate_fdi_teeth(cls, v: Dict[str, Any]) -> Dict[str, Any]:
        # Validamos códigos del sistema FDI (Adultos: 11-48, Niños: 51-85)
        valid_ranges = list(range(11, 19)) + list(range(21, 29)) + list(range(31, 39)) + list(range(41, 49)) + \
                       list(range(51, 56)) + list(range(61, 66)) + list(range(71, 76)) + list(range(81, 86))
        for tooth_num in v.keys():
            if not tooth_num.isdigit() or int(tooth_num) not in valid_ranges:
                raise ValueError(f"El número de diente {tooth_num} no es un código válido del sistema FDI.")
        return v

class OdontogramResponse(BaseModel):
    id: UUID
    patient_id: UUID
    tenant_id: UUID
    doctor_id: UUID
    description: Optional[str]
    teeth_data: Dict[str, Any]
    is_active: bool
    created_at: datetime
    updated_at: datetime

    model_config = {
        "from_attributes": True
    }
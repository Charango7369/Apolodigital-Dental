# app/modules/appointments/schemas.py
from pydantic import BaseModel, Field, model_validator
from uuid import UUID
from datetime import datetime
from typing import Optional

class AppointmentBase(BaseModel):
    patient_id: UUID
    doctor_id: UUID
    start_time: datetime = Field(..., description="Fecha y hora de inicio en UTC")
    end_time: datetime = Field(..., description="Fecha y hora de finalización en UTC")
    reason: Optional[str] = Field(None, description="Motivo de la consulta")

class AppointmentCreate(AppointmentBase):
    
    # 🛡️ Validación para evitar tiempos ilógicos
    @model_validator(mode='after')
    def check_time_logic(self) -> 'AppointmentCreate':
        if self.end_time <= self.start_time:
            raise ValueError('La hora de finalización debe ser posterior a la hora de inicio.')
        return self

class AppointmentUpdate(BaseModel):
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None
    status: Optional[str] = Field(None, pattern='^(PENDING|CONFIRMED|COMPLETED|CANCELLED|NO_SHOW)$')
    reason: Optional[str] = None

class AppointmentResponse(AppointmentBase):
    id: UUID
    tenant_id: UUID
    status: str
    is_active: bool
    created_at: datetime
    updated_at: datetime

    model_config = {
        "from_attributes": True
    }
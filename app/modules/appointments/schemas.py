# app/modules/appointments/schemas.py
from pydantic import BaseModel, Field, model_validator
from uuid import UUID
from datetime import datetime
from typing import Optional
from decimal import Decimal
from app.modules.patients.schemas import PatientResponse

class DoctorSummaryResponse(BaseModel):
    id: UUID
    full_name: str
    email: str

    model_config = {
        "from_attributes": True
    }

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

    @model_validator(mode='after')
    def check_time_logic(self) -> 'AppointmentUpdate':
        if self.start_time is not None and self.end_time is not None:
            if self.end_time <= self.start_time:
                raise ValueError('La hora de finalización debe ser posterior a la hora de inicio.')
        return self

class AppointmentRescheduleRequest(BaseModel):
    start_time: datetime = Field(..., description="Nueva fecha/hora de inicio en UTC")
    end_time: datetime = Field(..., description="Nueva fecha/hora de finalización en UTC")

    @model_validator(mode='after')
    def check_time_logic(self) -> 'AppointmentRescheduleRequest':
        if self.end_time <= self.start_time:
            raise ValueError('La hora de finalización debe ser posterior a la hora de inicio.')
        return self

class AppointmentCompleteRequest(BaseModel):
    final_cost: Decimal = Field(..., gt=0, description="Costo total final del tratamiento realizado")
    treatment_description: str = Field(..., min_length=3, description="Detalle clínico/financiero para la cuenta")

class AppointmentMetricsToday(BaseModel):
    total_today: int
    attended_today: int
    pending_today: int
    confirmed_today: int
    cancelled_today: int
    estimated_income_today: float

class AppointmentResponse(AppointmentBase):
    id: UUID
    tenant_id: UUID
    status: str
    is_active: bool
    created_at: datetime
    updated_at: datetime
    patient: Optional[PatientResponse] = None 
    doctor: Optional[DoctorSummaryResponse] = None

    model_config = {
        "from_attributes": True
    }

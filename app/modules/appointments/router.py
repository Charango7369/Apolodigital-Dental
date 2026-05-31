from fastapi import APIRouter
from pydantic import BaseModel
from typing import List, Optional
from datetime import datetime

# Definición correcta del router
router = APIRouter(prefix="/appointments", tags=["Appointments"])

class AppointmentBase(BaseModel):
    patient_id: int
    doctor_id: int
    start_time: datetime
    end_time: datetime
    reason: Optional[str] = None

class AppointmentCreate(AppointmentBase):
    pass

class Appointment(AppointmentBase):
    id: int
    status: str = "scheduled"

fake_db_appointments = []

@router.get("/", response_model=List[Appointment])
async def get_appointments():
    return fake_db_appointments

@router.post("/", response_model=Appointment)
async def create_appointment(appointment: AppointmentCreate):
    new_id = len(fake_db_appointments) + 1
    new_appointment = Appointment(id=new_id, **appointment.model_dump())
    fake_db_appointments.append(new_appointment)
    return new_appointment
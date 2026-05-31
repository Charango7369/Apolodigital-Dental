from fastapi import APIRouter
from pydantic import BaseModel
from typing import List, Optional

router = APIRouter(prefix="/patients", tags=["Patients"])

class PatientBase(BaseModel):
    first_name: str
    last_name: str
    email: Optional[str] = None
    phone: Optional[str] = None

class PatientCreate(PatientBase):
    pass

class Patient(PatientBase):
    id: int

fake_db_patients = []

@router.get("/", response_model=List[Patient])
async def get_patients():
    return fake_db_patients

@router.post("/", response_model=Patient)
async def create_patient(patient: PatientCreate):
    new_id = len(fake_db_patients) + 1
    new_patient = Patient(id=new_id, **patient.model_dump())
    fake_db_patients.append(new_patient)
    return new_patient
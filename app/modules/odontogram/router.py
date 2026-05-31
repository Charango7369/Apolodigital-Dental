from fastapi import APIRouter
from pydantic import BaseModel
from typing import List, Dict, Any

router = APIRouter(prefix="/odontogram", tags=["Odontogram"])

class OdontogramEntry(BaseModel):
    patient_id: int
    tooth_number: int
    surface: str
    condition: str
    notes: str = ""

class OdontogramCreate(OdontogramEntry):
    pass

class Odontogram(OdontogramEntry):
    id: int

fake_db_odonto = []

@router.get("/", response_model=List[Odontogram])
async def get_odontogram():
    return fake_db_odonto

@router.post("/", response_model=Odontogram)
async def create_entry(entry: OdontogramCreate):
    new_id = len(fake_db_odonto) + 1
    new_entry = Odontogram(id=new_id, **entry.model_dump())
    fake_db_odonto.append(new_entry)
    return new_entry
# app/modules/patients/router.py
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from uuid import UUID
from typing import List

from app.db.session import get_db
from app.modules.patients.schemas import PatientCreate, PatientUpdate, PatientResponse
from app.modules.patients.models import Patient as PatientModel

router = APIRouter(prefix="/patients", tags=["Patients"])

# ➕ 1. REGISTRAR UN NUEVO PACIENTE
@router.post("/", response_model=PatientResponse, status_code=status.HTTP_201_CREATED)
async def create_patient(patient: PatientCreate, db: AsyncSession = Depends(get_db)):
    db_patient = PatientModel(**patient.model_dump())
    db.add(db_patient)
    try:
        await db.commit()
        await db.refresh(db_patient)
        return db_patient
    except Exception as e:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Error al registrar al paciente: {str(e)}"
        )

# 🔍 2. OBTENER TODOS LOS PACIENTES DE UNA CLÍNICA
@router.post("/", response_model=PatientResponse, status_code=status.HTTP_201_CREATED)
async def create_patient(
    payload: PatientCreate, 
    db: AsyncSession = Depends(get_db),
    current_user: UserModel = Depends(get_current_user)
):
    # Desestructuramos el payload de Pydantic alineado a tu PatientBase
    new_patient = PatientModel(
        first_name=payload.first_name,
        last_name=payload.last_name,
        email=payload.email,
        phone=payload.phone,
        tenant_id=current_user.tenant_id,  # 👈 Inyección invisible y segura desde el JWT
        created_by=current_user.id         # 👈 Auditoría automática
    )
    
    db.add(new_patient)
    await db.commit()
    await db.refresh(new_patient)
    return new_patient

# 🎯 3. OBTENER UN PACIENTE ESPECÍFICO
@router.get("/{patient_id}", response_model=PatientResponse)
async def get_patient(patient_id: UUID, tenant_id: UUID, db: AsyncSession = Depends(get_db)):
    query = select(PatientModel).where(
        PatientModel.id == patient_id,
        PatientModel.tenant_id == tenant_id
    )
    result = await db.execute(query)
    patient = result.scalar_one_or_none()
    
    if not patient:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Paciente no encontrado o no pertenece a esta clínica"
        )
    return patient

# 📝 4. ACTUALIZAR DATOS DE UN PACIENTE
@router.put("/{patient_id}", response_model=PatientResponse)
async def update_patient(patient_id: UUID, tenant_id: UUID, patient_update: PatientUpdate, db: AsyncSession = Depends(get_db)):
    query = select(PatientModel).where(
        PatientModel.id == patient_id,
        PatientModel.tenant_id == tenant_id
    )
    result = await db.execute(query)
    db_patient = result.scalar_one_or_none()
    
    if not db_patient:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Paciente no encontrado"
        )
    
    update_data = patient_update.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(db_patient, key, value)
        
    try:
        await db.commit()
        await db.refresh(db_patient)
        return db_patient
    except Exception as e:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Error al actualizar los datos del paciente: {str(e)}"
        )

# ❌ 5. ELIMINAR PACIENTE
@router.delete("/{patient_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_patient(patient_id: UUID, tenant_id: UUID, db: AsyncSession = Depends(get_db)):
    query = select(PatientModel).where(
        PatientModel.id == patient_id,
        PatientModel.tenant_id == tenant_id
    )
    result = await db.execute(query)
    db_patient = result.scalar_one_or_none()
    
    if not db_patient:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Paciente no encontrado"
        )
    
    await db.delete(db_patient)
    await db.commit()
    return None
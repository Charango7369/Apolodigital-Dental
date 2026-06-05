# app/modules/patients/router.py
import traceback
from datetime import datetime, timezone
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from typing import List

from app.db.session import get_db
from app.modules.patients.models import Patient as PatientModel
# 🛡️ 1. CORREGIMOS LAS IMPORTACIONES ADICIONANDO PATIENTUPDATE:
from app.modules.patients.schemas import PatientCreate, PatientResponse, PatientUpdate
from app.modules.auth.dependencies import get_current_user
from app.modules.users.models import User as UserModel

router = APIRouter(prefix="/patients", tags=["Patients"])

# --- ENDPOINT: CREAR PACIENTE ---
@router.post("/", response_model=PatientResponse, status_code=status.HTTP_201_CREATED)
async def create_patient(
    payload: PatientCreate, 
    db: AsyncSession = Depends(get_db),
    current_user: UserModel = Depends(get_current_user)
):
    try:
        ahora = datetime.now(timezone.utc)
        new_patient = PatientModel(
            first_name=payload.first_name,
            last_name=payload.last_name,
            email=payload.email,
            phone=payload.phone
        )
        new_patient.tenant_id = current_user.tenant_id
        new_patient.created_by = current_user.id
        new_patient.is_active = True
        new_patient.created_at = ahora
        new_patient.updated_at = ahora

        db.add(new_patient)
        await db.commit()
        await db.refresh(new_patient)
        return new_patient
    except Exception as e:
        print("\n❌ ====== ¡FALLO EN RESPUESTA DE PACIENTE! ====== ❌")
        traceback.print_exc()
        print("❌ =================================================== \n")
        if isinstance(e, HTTPException):
            raise e
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))

# --- ENDPOINT: LISTAR PACIENTES ---
@router.get("/", response_model=List[PatientResponse])
async def get_my_patients(
    db: AsyncSession = Depends(get_db),
    current_user: UserModel = Depends(get_current_user)
):
    query = select(PatientModel).where(PatientModel.tenant_id == current_user.tenant_id)
    result = await db.execute(query)
    patients = result.scalars().all()
    
    # 🛡️ SALVAVIDAS: Saneamos los registros viejos en memoria antes de enviarlos a Pydantic
    ahora_mismo = datetime.now(timezone.utc)
    for p in patients:
        if getattr(p, 'is_active', None) is None:
            p.is_active = True
        if getattr(p, 'created_at', None) is None:
            p.created_at = ahora_mismo
        if getattr(p, 'updated_at', None) is None:
            p.updated_at = ahora_mismo
            
    return patients
# --- ENDPOINT: OBTENER UN PACIENTE POR ID ---
@router.get("/{patient_id}", response_model=PatientResponse)
async def get_patient_by_id(
    patient_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: UserModel = Depends(get_current_user)
):
    query = select(PatientModel).where(
        PatientModel.id == patient_id,
        PatientModel.tenant_id == current_user.tenant_id
    )
    result = await db.execute(query)
    patient = result.scalar_one_or_none()
    if not patient:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Paciente no encontrado en esta clínica")
    return patient

# 🔄 2. ENLACE CORREGIDO Y BLINDADO MULTI-TENANT PARA ACTUALIZACIÓN (Línea 86)
@router.patch("/{patient_id}", response_model=PatientResponse)
async def update_patient(
    patient_id: UUID,
    payload: PatientUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: UserModel = Depends(get_current_user) # 🔐 Extraemos el tenant de aquí de forma segura
):
    # Buscamos el paciente asegurando que pertenezca al tenant del doctor logueado (Evita IDOR)
    query = select(PatientModel).where(
        PatientModel.id == patient_id,
        PatientModel.tenant_id == current_user.tenant_id
    )
    result = await db.execute(query)
    patient = result.scalar_one_or_none()
    
    if not patient:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Paciente no encontrado")
    
    # Extraemos los datos enviados en el JSON omitiendo los que vengan nulos o no declarados
    update_data = payload.model_dump(exclude_unset=True)
    
    for key, value in update_data.items():
        setattr(patient, key, value)
        
    patient.updated_at = datetime.now(timezone.utc)
    patient.updated_by = current_user.id
    
    await db.commit()
    await db.refresh(patient)
    return patient
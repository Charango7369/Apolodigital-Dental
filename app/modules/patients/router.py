from pydantic import ValidationError
import traceback
from datetime import datetime, timezone
from uuid import UUID
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy import func, or_

from app.db.session import get_db
from app.modules.patients.models import Patient as PatientModel
# Importaciones consolidadas
from app.modules.patients.schemas import (
    PatientCreate, 
    PatientResponse, 
    PatientUpdate, 
    PaginatedPatientResponse
)
from app.modules.auth.dependencies import get_current_user
from app.modules.users.models import User as UserModel

router = APIRouter(prefix="/patients", tags=["Patients"])

# --- ENDPOINT: CREAR PACIENTE ---
@router.post("", response_model=PatientResponse, status_code=status.HTTP_201_CREATED)
async def create_patient(
    payload: PatientCreate,
    db: AsyncSession = Depends(get_db),
    current_user: UserModel = Depends(get_current_user)
):
    try:
        update_data = payload.model_dump(exclude_unset=True)
        
        new_patient = PatientModel(
            **update_data,
            tenant_id=current_user.tenant_id,
            is_active=True,
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc)
        )

        db.add(new_patient)
        await db.commit()
        await db.refresh(new_patient)

        return new_patient

    except Exception as e:
        await db.rollback()
        print("\n❌ ====== ERROR AL CREAR PACIENTE ====== ❌")
        traceback.print_exc()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, 
            detail=f"Fallo de integridad en base de datos: {str(e)}"
        )

# --- ENDPOINT: LISTAR PACIENTES (Paginado, Búsqueda y Filtro) ---
@router.get("", response_model=PaginatedPatientResponse)
async def get_my_patients(
    skip: int = 0,
    limit: int = 10,
    search: Optional[str] = None,
    active_only: bool = True,
    db: AsyncSession = Depends(get_db),
    current_user: UserModel = Depends(get_current_user)
):
    try:
        base_conditions = [PatientModel.tenant_id == current_user.tenant_id]
        
        if active_only:
            base_conditions.append(PatientModel.is_active == True)
            
        if search:
            search_term = f"%{search}%"
            base_conditions.append(
                or_(
                    PatientModel.first_name.ilike(search_term),
                    PatientModel.last_name.ilike(search_term),
                    PatientModel.phone.ilike(search_term)
                )
            )

        # 1. Contar el total absoluto para el frontend
        count_query = select(func.count(PatientModel.id)).where(*base_conditions)
        total_result = await db.execute(count_query)
        total_records = total_result.scalar() or 0

        # 2. Extraer solo la página solicitada
        query = select(PatientModel).where(*base_conditions)
        query = query.order_by(PatientModel.created_at.desc()).offset(skip).limit(limit)
        
        result = await db.execute(query)
        patients = result.scalars().all()
        
        ahora_mismo = datetime.now(timezone.utc)
        pacientes_validados = []
        
        for p in patients:
            if getattr(p, 'is_active', None) is None:
                p.is_active = True
            if getattr(p, 'created_at', None) is None:
                p.created_at = ahora_mismo
            if getattr(p, 'updated_at', None) is None:
                p.updated_at = ahora_mismo
                
            if getattr(p, 'email', None) == "":
                p.email = None
            if getattr(p, 'phone', None) == "":
                p.phone = None
                
            pacientes_validados.append(PatientResponse.model_validate(p))
                
        return {"total": total_records, "items": pacientes_validados}

    except ValidationError as ve:
        print("\n❌ ====== ERROR DE PYDANTIC (DATOS INCOMPATIBLES) ====== ❌")
        for error in ve.errors():
            print(f"Campo fallido: {error.get('loc')} -> Motivo: {error.get('msg')}")
        raise HTTPException(status_code=500, detail="Error de esquema en BD")
        
    except Exception as e:
        print("\n❌ ====== ERROR FATAL DE SQL/LÓGICA ====== ❌")
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))

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

# --- ENDPOINT: ACTUALIZAR PACIENTE ---
@router.patch("/{patient_id}", response_model=PatientResponse)
async def update_patient(
    patient_id: UUID,
    payload: PatientUpdate,
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
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Paciente no encontrado")
    
    update_data = payload.model_dump(exclude_unset=True)
    
    for key, value in update_data.items():
        setattr(patient, key, value)
        
    patient.updated_at = datetime.now(timezone.utc)
    
    await db.commit()
    await db.refresh(patient)
    return patient

# --- ENDPOINT: BAJA MÉDICA (SOFT DELETE) ---
@router.delete("/{patient_id}", status_code=status.HTTP_204_NO_CONTENT)
async def archive_patient(
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
        raise HTTPException(status_code=404, detail="Paciente no encontrado")
        
    patient.is_active = False
    patient.updated_at = datetime.now(timezone.utc)
    
    await db.commit()
    return None
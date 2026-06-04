# app/modules/patients/router.py
import traceback
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from uuid import UUID
from typing import List

from app.db.session import get_db
from app.modules.patients.schemas import PatientCreate, PatientUpdate, PatientResponse
from app.modules.patients.models import Patient as PatientModel
from app.modules.auth.dependencies import get_current_user
from app.modules.users.models import User as UserModel
router = APIRouter(prefix="/patients", tags=["Patients"])

# ➕ 1. REGISTRAR UN NUEVO PACIENTE
@router.post("/", response_model=PatientResponse, status_code=status.HTTP_201_CREATED)
async def create_patient(
    payload: PatientCreate, 
    db: AsyncSession = Depends(get_db),
    current_user: UserModel = Depends(get_current_user)
):
    try:
        # 1. Instanciamos el modelo con los datos core
        new_patient = PatientModel(
            first_name=payload.first_name,
            last_name=payload.last_name,
            email=payload.email,
            phone=payload.phone
        )
        
        # 2. Inyectamos los metadatos de seguridad y aislamiento
        new_patient.tenant_id = current_user.tenant_id
        new_patient.created_by = current_user.id
        
        # 🛡️ Salvavidas para Pydantic: Forzamos el estado activo en la instancia de Python
        new_patient.is_active = True

        # 3. Guardamos físicamente en Postgres en Railway
        db.add(new_patient)
        await db.commit()
        
        # 🔄 REFRESH CRÍTICO: Obligamos a SQLAlchemy a traer created_at y updated_at de la DB
        await db.refresh(new_patient)
        
        return new_patient

    except Exception as e:
        print("\n❌ ====== ¡FALLO EN RESPUESTA DE PACIENTE! ====== ❌")
        import traceback
        traceback.print_exc()
        print("❌ =================================================== \n")
        
        if isinstance(e, HTTPException):
            raise e
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Error en validación de respuesta: {str(e)}"
        )
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
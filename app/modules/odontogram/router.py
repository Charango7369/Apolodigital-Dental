# app/modules/odontograms/router.py
import logging
from datetime import datetime, timezone
from uuid import UUID
from typing import List

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from app.db.session import get_db
from app.modules.odontogram.models import Odontogram as OdontogramModel
from app.modules.odontogram.schemas import OdontogramCreate, OdontogramUpdate, OdontogramResponse
from app.modules.auth.dependencies import get_current_user, require_role
from app.modules.users.models import User as UserModel
from app.modules.patients.models import Patient as PatientModel

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/odontograms", tags=["Odontograms"])

require_doctor_or_admin = require_role(["DOCTOR", "ADMIN"])


# ➕ 1. REGISTRAR EVOLUCIÓN DE ODONTOGRAMA (Requiere DOCTOR o ADMIN + Anti-BOLA)
@router.post("/", response_model=OdontogramResponse, status_code=status.HTTP_201_CREATED)
async def create_odontogram(
    payload: OdontogramCreate,
    db: AsyncSession = Depends(get_db),
    current_user: UserModel = Depends(require_doctor_or_admin)
):
    try:
        ahora = datetime.now(timezone.utc)

        # 🛡️ ANTI-BOLA: Validar que el paciente pertenezca a la clínica del usuario en sesión
        patient_query = select(PatientModel).where(
            PatientModel.id == payload.patient_id,
            PatientModel.tenant_id == current_user.tenant_id,
            PatientModel.is_active == True
        )
        patient_exists = (await db.execute(patient_query)).scalar_one_or_none()
        if not patient_exists:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Paciente no encontrado en esta clínica."
            )

        # Mapeamos los sub-esquemas de Pydantic a un diccionario puro para Postgres JSONB
        serializable_teeth = {tooth: condition.model_dump() for tooth, condition in payload.teeth_data.items()}

        new_odontogram = OdontogramModel(
            patient_id=payload.patient_id,
            description=payload.description,
            teeth_data=serializable_teeth
        )

        # Inyección forzada del contexto de seguridad
        new_odontogram.tenant_id = current_user.tenant_id
        new_odontogram.doctor_id = current_user.id
        new_odontogram.created_by = current_user.id
        new_odontogram.is_active = True
        new_odontogram.created_at = ahora
        new_odontogram.updated_at = ahora

        db.add(new_odontogram)
        await db.commit()
        await db.refresh(new_odontogram)
        return new_odontogram

    except HTTPException:
        await db.rollback()
        raise
    except Exception as e:
        await db.rollback()
        logger.error(f"Fallo en registro de odontograma: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Error en el odontograma: {str(e)}"
        )


# 🔍 2. CONSULTAR HISTORIAL DE ODONTOGRAMAS DE UN PACIENTE (Aislamiento Multi-Tenant)
@router.get("/patient/{patient_id}", response_model=List[OdontogramResponse])
async def get_patient_odontograms(
    patient_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: UserModel = Depends(get_current_user)
):
    # 🛡️ Validar pertenencia del paciente al tenant
    patient_check = (await db.execute(
        select(PatientModel.id).where(
            PatientModel.id == patient_id,
            PatientModel.tenant_id == current_user.tenant_id
        )
    )).scalar_one_or_none()
    if not patient_check:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Paciente no encontrado en esta clínica."
        )

    # Forzar filtro estricto por tenant_id
    query = select(OdontogramModel).where(
        OdontogramModel.patient_id == patient_id,
        OdontogramModel.tenant_id == current_user.tenant_id
    ).order_by(OdontogramModel.created_at.desc())

    result = await db.execute(query)
    return result.scalars().all()


# ✏️ 3. EDITAR NOTAS DE UNA EVOLUCIÓN YA GUARDADA (Requiere DOCTOR o ADMIN)
@router.patch("/{odontogram_id}", response_model=OdontogramResponse)
async def update_odontogram_notes(
    odontogram_id: UUID,
    payload: OdontogramUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: UserModel = Depends(require_doctor_or_admin)
):
    query = select(OdontogramModel).where(
        OdontogramModel.id == odontogram_id,
        OdontogramModel.tenant_id == current_user.tenant_id
    )
    result = await db.execute(query)
    record = result.scalar_one_or_none()

    if not record:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Registro de odontograma no encontrado en esta clínica."
        )

    update_data = payload.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(record, key, value)

    record.updated_at = datetime.now(timezone.utc)

    try:
        await db.commit()
        await db.refresh(record)
        return record
    except Exception as e:
        await db.rollback()
        logger.error(f"Fallo al editar notas de odontograma: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Error al actualizar las notas: {str(e)}"
        )

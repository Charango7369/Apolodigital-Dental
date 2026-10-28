# app/modules/odontogram/router.py
import logging
from datetime import datetime, timezone
from uuid import UUID
from typing import List

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Request, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from app.db.session import get_db
from app.core.audit import record_medical_audit_event
from app.core.rate_limiter import get_client_ip
from app.modules.odontogram.models import Odontogram as OdontogramModel
from app.modules.odontogram.schemas import OdontogramCreate, OdontogramUpdate, OdontogramResponse
from app.modules.auth.dependencies import get_current_user, require_role
from app.modules.users.models import User as UserModel
from app.modules.patients.models import Patient as PatientModel

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/odontograms", tags=["Odontograms"])

require_doctor_or_admin = require_role(["DOCTOR", "ADMIN"])


# ➕ 1. REGISTRAR EVOLUCIÓN DE ODONTOGRAMA (Cifrado AES-256-GCM + Anti-BOLA + Auditoría HIPAA)
@router.post("/", response_model=OdontogramResponse, status_code=status.HTTP_201_CREATED)
async def create_odontogram(
    payload: OdontogramCreate,
    request: Request,
    background_tasks: BackgroundTasks,
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

        serializable_teeth = {tooth: condition.model_dump() for tooth, condition in payload.teeth_data.items()}

        new_odontogram = OdontogramModel(
            patient_id=payload.patient_id,
            description=payload.description,
            teeth_data=serializable_teeth  # Se cifra automáticamente vía EncryptedJSON TypeDecorator
        )

        new_odontogram.tenant_id = current_user.tenant_id
        new_odontogram.doctor_id = current_user.id
        new_odontogram.created_by = current_user.id
        new_odontogram.is_active = True
        new_odontogram.created_at = ahora
        new_odontogram.updated_at = ahora

        db.add(new_odontogram)
        await db.commit()
        await db.refresh(new_odontogram)

        # 📋 AUDITORÍA MÉDICA ASÍNCRONA (HIPAA / GDPR)
        background_tasks.add_task(
            record_medical_audit_event,
            user_id=current_user.id,
            tenant_id=current_user.tenant_id,
            action="CREATE",
            resource_type="ODONTOGRAM",
            resource_id=new_odontogram.id,
            patient_id=new_odontogram.patient_id,
            ip_address=get_client_ip(request),
            user_agent=request.headers.get("user-agent"),
            details={"teeth_affected_count": len(serializable_teeth)}
        )

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


# 🔍 2. CONSULTAR HISTORIAL DE ODONTOGRAMAS DE UN PACIENTE
@router.get("/patient/{patient_id}", response_model=List[OdontogramResponse])
async def get_patient_odontograms(
    patient_id: UUID,
    request: Request,
    background_tasks: BackgroundTasks,
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

    query = select(OdontogramModel).where(
        OdontogramModel.patient_id == patient_id,
        OdontogramModel.tenant_id == current_user.tenant_id
    ).order_by(OdontogramModel.created_at.desc())

    result = await db.execute(query)
    records = result.scalars().all()

    # 📋 AUDITORÍA MÉDICA ASÍNCRONA
    background_tasks.add_task(
        record_medical_audit_event,
        user_id=current_user.id,
        tenant_id=current_user.tenant_id,
        action="READ",
        resource_type="ODONTOGRAM_HISTORY",
        patient_id=patient_id,
        ip_address=get_client_ip(request),
        user_agent=request.headers.get("user-agent"),
        details={"records_retrieved": len(records)}
    )

    return records


# 🔍 3. CONSULTAR ODONTOGRAMA ESPECÍFICO POR ID
@router.get("/{odontogram_id}", response_model=OdontogramResponse)
async def get_odontogram_by_id(
    odontogram_id: UUID,
    request: Request,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
    current_user: UserModel = Depends(get_current_user)
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

    background_tasks.add_task(
        record_medical_audit_event,
        user_id=current_user.id,
        tenant_id=current_user.tenant_id,
        action="READ",
        resource_type="ODONTOGRAM",
        resource_id=record.id,
        patient_id=record.patient_id,
        ip_address=get_client_ip(request),
        user_agent=request.headers.get("user-agent"),
    )

    return record


# ✏️ 4. EDITAR NOTAS DE UNA EVOLUCIÓN (Requiere DOCTOR o ADMIN)
@router.patch("/{odontogram_id}", response_model=OdontogramResponse)
async def update_odontogram_notes(
    odontogram_id: UUID,
    payload: OdontogramUpdate,
    request: Request,
    background_tasks: BackgroundTasks,
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

        background_tasks.add_task(
            record_medical_audit_event,
            user_id=current_user.id,
            tenant_id=current_user.tenant_id,
            action="UPDATE",
            resource_type="ODONTOGRAM",
            resource_id=record.id,
            patient_id=record.patient_id,
            ip_address=get_client_ip(request),
            user_agent=request.headers.get("user-agent"),
            details={"updated_fields": list(update_data.keys())}
        )

        return record
    except Exception as e:
        await db.rollback()
        logger.error(f"Fallo al editar notas de odontograma: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Error al actualizar las notas: {str(e)}"
        )

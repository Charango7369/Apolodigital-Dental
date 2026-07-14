# app/modules/odontograms/router.py
import traceback
from datetime import datetime, timezone
from uuid import UUID
from typing import List

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from app.db.session import get_db
from app.modules.odontogram.models import Odontogram as OdontogramModel
from app.modules.odontogram.schemas import OdontogramCreate, OdontogramUpdate, OdontogramResponse
from app.modules.auth.dependencies import get_current_user
from app.modules.users.models import User as UserModel

router = APIRouter(prefix="/odontograms", tags=["Odontograms"])

# ➕ 1. REGISTRAR EVOLUCIÓN DE ODONTOGRAMA
@router.post("/", response_model=OdontogramResponse, status_code=status.HTTP_201_CREATED)
async def create_odontogram(
    payload: OdontogramCreate,
    db: AsyncSession = Depends(get_db),
    current_user: UserModel = Depends(get_current_user)
):
    try:
        ahora = datetime.now(timezone.utc)

        # Mapeamos los sub-esquemas de Pydantic a un diccionario puro para que Postgres JSONB lo entienda
        serializable_teeth = {tooth: condition.model_dump() for tooth, condition in payload.teeth_data.items()}

        new_odontogram = OdontogramModel(
            patient_id=payload.patient_id,
            description=payload.description,
            teeth_data=serializable_teeth
        )

        # Inyección imperativa del contexto de seguridad
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

    except Exception as e:
        print("\n❌ ====== ¡FALLO EN REGISTRO DE ODONTOGRAMA! ====== ❌")
        traceback.print_exc()
        print("❌ =================================================== \n")
        if isinstance(e, HTTPException):
            raise e
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Error en el odontograma: {str(e)}")


# 🔍 2. CONSULTAR HISTORIAL DE ODONTOGRAMAS DE UN PACIENTE (Aislamiento Multi-Tenant)
@router.get("/patient/{patient_id}", response_model=List[OdontogramResponse])
async def get_patient_odontograms(
    patient_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: UserModel = Depends(get_current_user)
):
    # Buscamos todos los registros históricos del paciente pero forzando que pertenezcan a la clínica actual
    query = select(OdontogramModel).where(
        OdontogramModel.patient_id == patient_id,
        OdontogramModel.tenant_id == current_user.tenant_id
    ).order_by(OdontogramModel.created_at.desc())

    result = await db.execute(query)
    return result.scalars().all()


# ✏️ 3. EDITAR NOTAS DE UNA EVOLUCIÓN YA GUARDADA
# 🚨 NUEVO: permite corregir/agregar las notas de un registro existente
# (por ejemplo uno que quedó marcado como "Sin notas"). Deliberadamente NO
# permite tocar teeth_data — el estado dental siempre se versiona con una
# nueva evolución, nunca se reescribe el pasado.
@router.patch("/{odontogram_id}", response_model=OdontogramResponse)
async def update_odontogram_notes(
    odontogram_id: UUID,
    payload: OdontogramUpdate,
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
        print("\n❌ ====== ¡FALLO AL EDITAR NOTAS DEL ODONTOGRAMA! ====== ❌")
        traceback.print_exc()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Error al actualizar las notas: {str(e)}"
        )
# app/modules/odontograms/router.py
import traceback
from datetime import datetime, timezone
from uuid import UUID
from typing import List

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from app.db.session import get_db
from app.modules.odontograms.models import Odontogram as OdontogramModel
from app.modules.odontograms.schemas import OdontogramCreate, OdontogramResponse
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
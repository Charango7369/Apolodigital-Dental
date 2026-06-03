# app/modules/odontogram/router.py
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from uuid import UUID
from typing import List

from app.db.session import get_db
from app.modules.odontogram.schemas import OdontogramEntryCreate, OdontogramEntryUpdate, OdontogramEntryResponse
from app.modules.odontogram.models import OdontogramEntry as OdontogramEntryModel

router = APIRouter(prefix="/odontogram", tags=["Odontogram"])

# ➕ 1. REGISTRAR UN HALLAZGO EN EL ODONTOGRAMA
@router.post("/", response_model=OdontogramEntryResponse, status_code=status.HTTP_201_CREATED)
async def create_odontogram_entry(entry: OdontogramEntryCreate, db: AsyncSession = Depends(get_db)):
    db_entry = OdontogramEntryModel(**entry.model_dump())
    db.add(db_entry)
    try:
        await db.commit()
        await db.refresh(db_entry)
        return db_entry
    except Exception as e:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Error al registrar la entrada en el odontograma: {str(e)}"
        )

# 🔍 2. OBTENER EL HISTORIAL COMPLETO DE UN PACIENTE (Para cargar el Odontograma)
@router.get("/patient/{patient_id}", response_model=List[OdontogramEntryResponse])
async def get_patient_odontogram(patient_id: UUID, tenant_id: UUID, db: AsyncSession = Depends(get_db)):
    # 🚨 DOBLE CANDADO: Filtra estrictamente por paciente y por clínica (Tenant)
    query = select(OdontogramEntryModel).where(
        OdontogramEntryModel.patient_id == patient_id,
        OdontogramEntryModel.tenant_id == tenant_id
    )
    result = await db.execute(query)
    entries = result.scalars().all()
    return entries

# 📝 3. ACTUALIZAR UN DIENTE ESPECÍFICO
@router.put("/{entry_id}", response_model=OdontogramEntryResponse)
async def update_odontogram_entry(entry_id: UUID, tenant_id: UUID, entry_update: OdontogramEntryUpdate, db: AsyncSession = Depends(get_db)):
    query = select(OdontogramEntryModel).where(
        (OdontogramEntryModel.id == entry_id) & 
        (OdontogramEntryModel.tenant_id == tenant_id)
    )
    result = await db.execute(query)
    db_entry = result.scalar_one_or_none()
    
    if not db_entry:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Registro de odontograma no encontrado o acceso denegado"
        )
    
    update_data = entry_update.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(db_entry, key, value)
        
    try:
        await db.commit()
        await db.refresh(db_entry)
        return db_entry
    except Exception as e:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Error al actualizar el registro clínico: {str(e)}"
        )

# ❌ 4. ELIMINAR UN REGISTRO (Ej. Si el dentista se equivocó de diagnóstico)
@router.delete("/{entry_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_odontogram_entry(entry_id: UUID, tenant_id: UUID, db: AsyncSession = Depends(get_db)):
    query = select(OdontogramEntryModel).where(
        (OdontogramEntryModel.id == entry_id) & 
        (OdontogramEntryModel.tenant_id == tenant_id)
    )
    result = await db.execute(query)
    db_entry = result.scalar_one_or_none()
    
    if not db_entry:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Registro no encontrado"
        )
    
    await db.delete(db_entry)
    await db.commit()
    return None
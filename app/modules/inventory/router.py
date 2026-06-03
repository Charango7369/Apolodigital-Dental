from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from uuid import UUID
from typing import List

from app.db.session import get_db
from app.modules.inventory.schemas import InventoryItemCreate, InventoryItemUpdate, InventoryItemResponse
from app.modules.inventory.models import InventoryItem as InventoryItemModel

router = APIRouter(prefix="/inventory", tags=["Inventory"])

# ➕ 1. CREAR INSUMO
@router.post("/", response_model=InventoryItemResponse, status_code=status.HTTP_201_CREATED)
async def create_item(item: InventoryItemCreate, db: AsyncSession = Depends(get_db)):
    db_item = InventoryItemModel(**item.model_dump())
    db.add(db_item)
    try:
        await db.commit()
        await db.refresh(db_item)
        return db_item
    except Exception as e:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Error al crear el insumo: {str(e)}"
        )

# 🔍 2. OBTENER TODO EL INVENTARIO DE UNA CLÍNICA (Filtrado Obligatorio)
@router.get("/", response_model=List[InventoryItemResponse])
async def get_inventory_by_tenant(tenant_id: UUID, db: AsyncSession = Depends(get_db)):
    # 🚨 FILTRO CRUCIAL: Solo se traen los ítems que pertenezcan al tenant_id solicitado
    query = select(InventoryItemModel).where(InventoryItemModel.tenant_id == tenant_id)
    result = await db.execute(query)
    items = result.scalars().all()
    return items

# 🎯 3. OBTENER UN INSUMO ESPECÍFICO
@router.get("/{item_id}", response_model=InventoryItemResponse)
async def get_item(item_id: UUID, tenant_id: UUID, db: AsyncSession = Depends(get_db)):
    query = select(InventoryItemModel).where(
        InventoryItemModel.id == item_id, 
        InventoryItemModel.tenant_id == tenant_id
    )
    result = await db.execute(query)
    item = result.scalar_one_or_none()
    
    if not item:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Insumo no encontrado o no pertenece a esta clínica"
        )
    return item

# 📝 4. ACTUALIZAR INSUMO
@router.put("/{item_id}", response_model=InventoryItemResponse)
async def update_item(item_id: UUID, tenant_id: UUID, item_update: InventoryItemUpdate, db: AsyncSession = Depends(get_db)):
    query = select(InventoryItemModel).where(
        InventoryItemModel.id == item_id, 
        InventoryItemModel.tenant_id == tenant_id
    )
    result = await db.execute(query)
    db_item = result.scalar_one_or_none()
    
    if not db_item:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Insumo no encontrado"
        )
    
    # Aplicamos solo los campos enviados por el frontend
    update_data = item_update.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(db_item, key, value)
        
    try:
        await db.commit()
        await db.refresh(db_item)
        return db_item
    except Exception as e:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Error al actualizar el insumo: {str(e)}"
        )
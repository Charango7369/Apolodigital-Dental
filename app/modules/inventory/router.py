# app/modules/inventory/router.py
import traceback
from datetime import datetime, timezone
from uuid import UUID
from typing import List

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from app.db.session import get_db
from app.modules.inventory.models import InventoryItem as InventoryModel
from app.modules.inventory.schemas import InventoryCreate, InventoryResponse, InventoryUpdate
from app.modules.auth.dependencies import get_current_user
from app.modules.users.models import User as UserModel

router = APIRouter(prefix="/inventory", tags=["Inventory"])

# ➕ 1. CREAR INSUMO (Inyección invisible de Tenant y Auditoría)
@router.post("/", response_model=InventoryResponse, status_code=status.HTTP_201_CREATED)
async def create_inventory_item(
    payload: InventoryCreate, 
    db: AsyncSession = Depends(get_db),
    current_user: UserModel = Depends(get_current_user)
):
    try:
        ahora = datetime.now(timezone.utc)
        
        # Instanciamos el modelo con los datos core numéricos y de texto
        new_item = InventoryModel(
            item_name=payload.item_name,
            sku=payload.sku,
            stock=payload.stock,
            stock_alert=payload.stock_alert,
            price=payload.price
        )
        
        # Inyectamos de forma imperativa el aislamiento y control de tiempos
        new_item.tenant_id = current_user.tenant_id
        new_item.created_by = current_user.id
        new_item.is_active = True
        new_item.created_at = ahora
        new_item.updated_at = ahora

        db.add(new_item)
        await db.commit()
        await db.refresh(new_item)
        return new_item

    except Exception as e:
        print("\n❌ ====== ¡FALLO EN RESPUESTA DE INVENTARIO! ====== ❌")
        traceback.print_exc()
        print("❌ =================================================== \n")
        if isinstance(e, HTTPException):
            raise e
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, 
            detail=f"Error al registrar insumo: {str(e)}"
        )

# 🔍 2. LISTAR INVENTARIO (Filtro absoluto por clínica)
@router.get("/", response_model=List[InventoryResponse])
async def get_my_inventory(
    db: AsyncSession = Depends(get_db),
    current_user: UserModel = Depends(get_current_user)
):
    query = select(InventoryModel).where(InventoryModel.tenant_id == current_user.tenant_id)
    result = await db.execute(query)
    return result.scalars().all()

# 🎯 3. OBTENER UN INSUMO POR ID (Filtro anti-IDOR)
@router.get("/{item_id}", response_model=InventoryResponse)
async def get_inventory_item_by_id(
    item_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: UserModel = Depends(get_current_user)
):
    query = select(InventoryModel).where(
        InventoryModel.id == item_id,
        InventoryModel.tenant_id == current_user.tenant_id
    )
    result = await db.execute(query)
    item = result.scalar_one_or_none()
    
    if not item:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, 
            detail="Insumo no encontrado en esta clínica"
        )
    return item

# 🔄 4. ACTUALIZAR INSUMO (Modificación parcial segura)
@router.patch("/{item_id}", response_model=InventoryResponse)
async def update_inventory_item(
    item_id: UUID,
    payload: InventoryUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: UserModel = Depends(get_current_user)
):
    query = select(InventoryModel).where(
        InventoryModel.id == item_id,
        InventoryModel.tenant_id == current_user.tenant_id
    )
    result = await db.execute(query)
    item = result.scalar_one_or_none()
    
    if not item:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, 
            detail="Insumo no encontrado"
        )
    
    # Dump de Pydantic abstrayendo solo los campos que el cliente editó
    update_data = payload.model_dump(exclude_unset=True)
    
    for key, value in update_data.items():
        setattr(item, key, value)
        
    item.updated_at = datetime.now(timezone.utc)
    item.updated_by = current_user.id
    
    await db.commit()
    await db.refresh(item)
    return item
# app/modules/inventory/schemas.py
from pydantic import BaseModel, Field
from uuid import UUID
from datetime import datetime
from typing import Optional

# 1. Esquema Base
class InventoryItemBase(BaseModel):
    name: str = Field(..., description="Nombre del insumo médico (ej. Guantes de látex)")
    stock: int = Field(default=0, ge=0, description="Cantidad disponible en inventario")

# 2. Esquema para Crear (¡Esta es la clase que te está pidiendo el router!)
class InventoryItemCreate(InventoryItemBase):
    tenant_id: UUID

# 3. Esquema para Actualizar
class InventoryItemUpdate(BaseModel):
    name: Optional[str] = None
    stock: Optional[int] = Field(None, ge=0)
    is_active: Optional[bool] = None

# 4. Esquema para Respuesta
class InventoryItemResponse(InventoryItemBase):
    id: UUID
    tenant_id: UUID
    is_active: bool
    created_at: datetime
    updated_at: datetime

    model_config = {
        "from_attributes": True
    }
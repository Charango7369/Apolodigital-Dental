# app/modules/inventory/schemas.py
from pydantic import BaseModel, Field
from uuid import UUID
from datetime import datetime
from typing import Optional
from decimal import Decimal

class InventoryBase(BaseModel):
    item_name: str = Field(..., max_length=255, description="Nombre del insumo dental")
    sku: Optional[str] = Field(None, max_length=100, description="Código único o SKU")
    stock: int = Field(0, ge=0, description="Cantidad disponible")
    stock_alert: int = Field(5, ge=0, description="Umbral mínimo para alerta")
    price: Decimal = Field(Decimal("0.00"), ge=0, description="Precio o costo por unidad")

class InventoryCreate(InventoryBase):
    pass  # El frontend no manda tenant_id, lo inyecta el token en secreto

class InventoryUpdate(BaseModel):
    item_name: Optional[str] = Field(None, max_length=255)
    sku: Optional[str] = Field(None, max_length=100)
    stock: Optional[int] = Field(None, ge=0)
    stock_alert: Optional[int] = Field(None, ge=0)
    price: Optional[Decimal] = Field(None, ge=0)
    is_active: Optional[bool] = None

class InventoryResponse(InventoryBase):
    id: UUID
    tenant_id: UUID
    is_active: bool
    created_at: datetime
    updated_at: datetime

    model_config = {
        "from_attributes": True
    }
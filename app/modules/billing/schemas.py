from pydantic import BaseModel, Field
from uuid import UUID
from datetime import datetime
from decimal import Decimal
from typing import Optional

# Esquema base con los campos comunes
class InvoiceBase(BaseModel):
    invoice_number: str = Field(..., description="Número correlativo de la factura (ej. FAC-001)")
    total_amount: Decimal = Field(..., max_digits=10, decimal_places=2, description="Monto total del cobro")
    status: str = Field(default="pending", description="Estado actual: pending, paid, cancelled")

# Esquema para crear una factura
class InvoiceCreate(InvoiceBase):
    tenant_id: UUID

# Esquema para actualizar (Útil para cambiar el estado del pago o el monto)
class InvoiceUpdate(BaseModel):
    total_amount: Optional[Decimal] = Field(None, max_digits=10, decimal_places=2)
    status: Optional[str] = None # Ej. cambiar de 'pending' a 'paid'
    is_active: Optional[bool] = None

# Esquema de respuesta para el Frontend
class InvoiceResponse(InvoiceBase):
    id: UUID
    tenant_id: UUID
    is_active: bool
    created_at: datetime
    updated_at: datetime

    model_config = {
        "from_attributes": True
    }
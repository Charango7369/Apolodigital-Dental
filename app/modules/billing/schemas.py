# app/modules/billing/schemas.py
from pydantic import BaseModel, Field
from uuid import UUID
from typing import Optional, List
from datetime import datetime
from decimal import Decimal

# --- ESQUEMAS PARA PAGOS (PAYMENTS) ---
class PaymentCreate(BaseModel):
    amount_paid: Decimal = Field(..., gt=0, description="Monto pagado. Debe ser mayor a 0.")
    payment_method: str = Field(..., pattern="^(CASH|QR|CARD|TRANSFER)$")
    reference_number: Optional[str] = None
    notes: Optional[str] = None

class PaymentResponse(BaseModel):
    id: UUID
    account_id: UUID
    amount_paid: Decimal
    payment_method: str
    reference_number: Optional[str]
    notes: Optional[str]
    created_at: datetime
    created_by: Optional[UUID]

    model_config = {
        "from_attributes": True
    }

# --- ESQUEMAS PARA CUENTAS POR COBRAR (ACCOUNTS RECEIVABLE) ---
class AccountCreate(BaseModel):
    patient_id: UUID
    total_amount: Decimal = Field(..., gt=0, description="Costo total del tratamiento")
    description: str = Field(..., min_length=3)

class AccountResponse(BaseModel):
    id: UUID
    patient_id: UUID
    total_amount: Decimal
    balance_due: Decimal
    status: str
    description: str
    created_at: datetime
    payments: List[PaymentResponse] = [] # Incluimos el historial de abonos

    model_config = {
        "from_attributes": True
    }
class InvoiceCreate(BaseModel):
    account_id: UUID
    issue_date: datetime
    due_date: datetime
    # ... otros campos que necesites ...
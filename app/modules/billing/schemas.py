# app/modules/billing/schemas.py
from pydantic import BaseModel, Field, field_serializer
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

    # 🚨 FIX: Decimal se serializa como string en JSON por defecto.
    # Lo convertimos a float para que el frontend pueda sumar/formatear sin NaN.
    @field_serializer('amount_paid')
    def serialize_amount_paid(self, v: Decimal, _info):
        return float(v)

    model_config = {
        "from_attributes": True
    }

# --- MINI-PACIENTE (para no sobrecargar la respuesta) ---
class PatientMini(BaseModel):
    id: UUID
    first_name: str
    last_name: str
    phone: Optional[str] = None

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
    payments: List[PaymentResponse] = []
    patient: Optional[PatientMini] = None  # 🚨 Nombre del paciente para la UI

    # 🚨 FIX: mismo problema — Decimal a float para evitar NaN en el frontend
    @field_serializer('total_amount', 'balance_due')
    def serialize_amounts(self, v: Decimal, _info):
        return float(v)

    model_config = {
        "from_attributes": True
    }

class InvoiceCreate(BaseModel):
    account_id: UUID
    issue_date: datetime
    due_date: datetime
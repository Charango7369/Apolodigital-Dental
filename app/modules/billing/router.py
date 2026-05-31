from fastapi import APIRouter
from pydantic import BaseModel
from typing import List, Optional

router = APIRouter(prefix="/billing", tags=["Billing"])

class InvoiceBase(BaseModel):
    patient_id: int
    amount: float
    description: str
    is_paid: bool = False

class InvoiceCreate(InvoiceBase):
    pass

class Invoice(InvoiceBase):
    id: int

fake_db_invoices = []

@router.get("/", response_model=List[Invoice])
async def get_invoices():
    return fake_db_invoices

@router.post("/", response_model=Invoice)
async def create_invoice(invoice: InvoiceCreate):
    new_id = len(fake_db_invoices) + 1
    new_invoice = Invoice(id=new_id, **invoice.model_dump())
    fake_db_invoices.append(new_invoice)
    return new_invoice
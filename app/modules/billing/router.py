from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from uuid import UUID
from typing import List

from app.db.session import get_db
from app.modules.billing.schemas import InvoiceCreate, InvoiceUpdate, InvoiceResponse
from app.modules.billing.models import Invoice as InvoiceModel

router = APIRouter(prefix="/billing", tags=["Billing"])

# ➕ 1. CREAR FACTURA / COBRO
@router.post("/", response_model=InvoiceResponse, status_code=status.HTTP_201_CREATED)
async def create_invoice(invoice: InvoiceCreate, db: AsyncSession = Depends(get_db)):
    db_invoice = InvoiceModel(**invoice.model_dump())
    db.add(db_invoice)
    try:
        await db.commit()
        await db.refresh(db_invoice)
        return db_invoice
    except Exception as e:
        await db.rollback()
        # Captura si el invoice_number ya existe (Restricción UNIQUE)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Error al registrar la factura (verifica si el número está duplicado): {str(e)}"
        )

# 🔍 2. OBTENER TODAS LAS FACTURAS DE UNA CLÍNICA
@router.get("/", response_model=List[InvoiceResponse])
async def get_invoices_by_tenant(tenant_id: UUID, db: AsyncSession = Depends(get_db)):
    # 🚨 FILTRO MULTI-TENANT: Solo facturas de la clínica solicitante
    query = select(InvoiceModel).where(InvoiceModel.tenant_id == tenant_id)
    result = await db.execute(query)
    invoices = result.scalars().all()
    return invoices

# 🎯 3. OBTENER UNA FACTURA ESPECÍFICA
@router.get("/{invoice_id}", response_model=InvoiceResponse)
async def get_invoice(invoice_id: UUID, tenant_id: UUID, db: AsyncSession = Depends(get_db)):
    query = select(InvoiceModel).where(
        InvoiceModel.id == invoice_id, 
        InvoiceModel.tenant_id == tenant_id
    )
    result = await db.execute(query)
    invoice = result.scalar_one_or_none()
    
    if not invoice:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Factura no encontrada o no pertenece a esta clínica"
        )
    return invoice

# 📝 4. ACTUALIZAR FACTURA (Ej. Registrar pago o cancelarla)
@router.put("/{invoice_id}", response_model=InvoiceResponse)
async def update_invoice(invoice_id: UUID, tenant_id: UUID, invoice_update: InvoiceUpdate, db: AsyncSession = Depends(get_db)):
    query = select(InvoiceModel).where(
        InvoiceModel.id == invoice_id, 
        InvoiceModel.tenant_id == tenant_id
    )
    result = await db.execute(query)
    db_invoice = result.scalar_one_or_none()
    
    if not db_invoice:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Factura no encontrada"
        )
    
    update_data = invoice_update.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(db_invoice, key, value)
        
    try:
        await db.commit()
        await db.refresh(db_invoice)
        return db_invoice
    except Exception as e:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Error al actualizar la factura: {str(e)}"
        )
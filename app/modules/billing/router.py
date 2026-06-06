# app/modules/billing/router.py
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy.orm import selectinload
from uuid import UUID
from typing import List

from app.db.session import get_db

from app.modules.billing.schemas import AccountCreate, AccountResponse, PaymentCreate, PaymentResponse
# Importamos los modelos con los nombres exactos de tu models.py
from app.modules.billing.models import AccountReceivable, Payment

router = APIRouter(prefix="/billing", tags=["Billing / Cuentas"])

# ➕ 1. CREAR CUENTA POR COBRAR (NUEVO TRATAMIENTO/DEUDA)
@router.post("/accounts", response_model=AccountResponse, status_code=status.HTTP_201_CREATED)
async def create_account(account: AccountCreate, tenant_id: UUID, db: AsyncSession = Depends(get_db)):
    account_data = account.model_dump()
    account_data["tenant_id"] = tenant_id 
    
    # 💡 Lógica de negocio: Al nacer la cuenta, el saldo pendiente es igual al costo total
    account_data["balance_due"] = account_data["total_amount"]
    account_data["status"] = "PENDING"
    
    db_account = AccountReceivable(**account_data)
    db.add(db_account)
    try:
        await db.commit()
        await db.refresh(db_account)
        return db_account
    except Exception as e:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Error al registrar la cuenta: {str(e)}"
        )

# 🔍 2. OBTENER TODAS LAS CUENTAS DE LA CLÍNICA
@router.get("/accounts", response_model=List[AccountResponse])
async def get_accounts_by_tenant(tenant_id: UUID, db: AsyncSession = Depends(get_db)):
    # 💡 Usamos selectinload para cargar el historial de pagos sin romper la sesión asíncrona
    query = (
        select(AccountReceivable)
        .where(AccountReceivable.tenant_id == tenant_id)
        .options(selectinload(AccountReceivable.payments))
    )
    result = await db.execute(query)
    accounts = result.scalars().all()
    return accounts

# 🎯 3. OBTENER UNA CUENTA ESPECÍFICA CON SU HISTORIAL DE PAGOS
@router.get("/accounts/{account_id}", response_model=AccountResponse)
async def get_account(account_id: UUID, tenant_id: UUID, db: AsyncSession = Depends(get_db)):
    query = (
        select(AccountReceivable)
        .where(
            AccountReceivable.id == account_id, 
            AccountReceivable.tenant_id == tenant_id
        )
        .options(selectinload(AccountReceivable.payments))
    )
    result = await db.execute(query)
    account = result.scalar_one_or_none()
    
    if not account:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Cuenta no encontrada o no pertenece a esta clínica"
        )
    return account

# 💰 4. REGISTRAR UN PAGO Y DESCONTAR SALDO
@router.post("/accounts/{account_id}/payments", response_model=PaymentResponse, status_code=status.HTTP_201_CREATED)
async def create_payment(account_id: UUID, tenant_id: UUID, payment: PaymentCreate, db: AsyncSession = Depends(get_db)):
    # 1. Buscamos la cuenta
    query = select(AccountReceivable).where(
        AccountReceivable.id == account_id,
        AccountReceivable.tenant_id == tenant_id
    )
    result = await db.execute(query)
    db_account = result.scalar_one_or_none()

    if not db_account:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Cuenta no encontrada o no pertenece a esta clínica"
        )

    # 2. Validamos que el pago no sea mayor a la deuda restante (Opcional, pero recomendado)
    if payment.amount_paid > db_account.balance_due:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"El abono ({payment.amount_paid}) supera el saldo pendiente ({db_account.balance_due})"
        )

    # 3. Creamos el registro del pago
    payment_data = payment.model_dump()
    payment_data["account_id"] = account_id
    payment_data["tenant_id"] = tenant_id

    db_payment = Payment(**payment_data)
    db.add(db_payment)
    
    # 4. 💡 Actualizamos el estado financiero de la cuenta
    db_account.balance_due -= payment.amount_paid
    
    # Si la deuda llegó a cero, la marcamos como pagada
    if db_account.balance_due == 0:
        db_account.status = "PAID"
    elif db_account.balance_due < db_account.total_amount:
        db_account.status = "PARTIAL"
        
    try:
        await db.commit()
        await db.refresh(db_payment)
        return db_payment
    except Exception as e:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Error al registrar el pago: {str(e)}"
        )
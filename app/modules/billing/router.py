# app/modules/billing/router.py
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy.orm import selectinload
from uuid import UUID
from typing import List, Optional

from app.db.session import get_db
from app.modules.auth.dependencies import get_current_user, require_role
from app.modules.users.models import User as UserModel
from app.modules.patients.models import Patient as PatientModel

from app.modules.billing.schemas import (
    AccountCreate, AccountResponse, PaymentCreate, PaymentResponse, PatientMini
)
from app.modules.billing.models import AccountReceivable, Payment

router = APIRouter(prefix="/billing", tags=["Billing / Cuentas"])


# ─── Helper: adjunta el paciente a cada cuenta (aislado por tenant) ─────────
async def _attach_patients(db: AsyncSession, accounts: List[AccountReceivable], tenant_id: UUID) -> List[AccountResponse]:
    patient_ids = {acc.patient_id for acc in accounts}
    patients_map = {}

    if patient_ids:
        result = await db.execute(
            select(PatientModel).where(
                PatientModel.id.in_(patient_ids),
                PatientModel.tenant_id == tenant_id
            )
        )
        for p in result.scalars().all():
            patients_map[p.id] = PatientMini.model_validate(p)

    responses = []
    for acc in accounts:
        resp = AccountResponse.model_validate(acc)
        resp.patient = patients_map.get(acc.patient_id)
        responses.append(resp)
    return responses


# ➕ 1. CREAR CUENTA POR COBRAR (uso manual, con validación anti-BOLA)
@router.post("/accounts", response_model=AccountResponse, status_code=status.HTTP_201_CREATED)
async def create_account(
    account: AccountCreate,
    db: AsyncSession = Depends(get_db),
    current_user: UserModel = Depends(require_role(["ADMIN", "RECEPTIONIST"])),
):
    # 🛡️ ANTI-BOLA: Validar que el paciente pertenezca a la clínica del usuario autenticado
    patient_query = select(PatientModel).where(
        PatientModel.id == account.patient_id,
        PatientModel.tenant_id == current_user.tenant_id,
        PatientModel.is_active == True
    )
    patient_exists = (await db.execute(patient_query)).scalar_one_or_none()
    if not patient_exists:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Paciente no encontrado en esta clínica."
        )

    account_data = account.model_dump()
    account_data["tenant_id"] = current_user.tenant_id
    account_data["balance_due"] = account_data["total_amount"]
    account_data["status"] = "PENDING"

    db_account = AccountReceivable(**account_data)
    db.add(db_account)
    try:
        await db.commit()
        await db.refresh(db_account)
        attached = await _attach_patients(db, [db_account], current_user.tenant_id)
        return attached[0]
    except Exception as e:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Error al registrar la cuenta: {str(e)}"
        )


# 🔍 2. OBTENER TODAS LAS CUENTAS DE LA CLÍNICA (con filtro opcional de estado)
@router.get("/accounts", response_model=List[AccountResponse])
async def get_accounts_by_tenant(
    status_filter: Optional[str] = None,  # PENDING | PARTIAL | PAID
    db: AsyncSession = Depends(get_db),
    current_user: UserModel = Depends(get_current_user),
):
    conditions = [
        AccountReceivable.tenant_id == current_user.tenant_id,
        AccountReceivable.is_active == True,
    ]
    if status_filter:
        conditions.append(AccountReceivable.status == status_filter)

    query = (
        select(AccountReceivable)
        .where(*conditions)
        .options(selectinload(AccountReceivable.payments))
        .order_by(AccountReceivable.created_at.desc())
    )
    result = await db.execute(query)
    accounts = result.scalars().all()
    return await _attach_patients(db, accounts, current_user.tenant_id)


# 🎯 3. OBTENER UNA CUENTA ESPECÍFICA CON SU HISTORIAL DE PAGOS
@router.get("/accounts/{account_id}", response_model=AccountResponse)
async def get_account(
    account_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: UserModel = Depends(get_current_user),
):
    query = (
        select(AccountReceivable)
        .where(
            AccountReceivable.id == account_id,
            AccountReceivable.tenant_id == current_user.tenant_id,
        )
        .options(selectinload(AccountReceivable.payments))
    )
    result = await db.execute(query)
    account = result.scalar_one_or_none()

    if not account:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Cuenta no encontrada en esta clínica."
        )

    attached = await _attach_patients(db, [account], current_user.tenant_id)
    return attached[0]


# 🩺 3b. HISTORIAL DE CUENTAS DE UN PACIENTE ESPECÍFICO
@router.get("/accounts/patient/{patient_id}", response_model=List[AccountResponse])
async def get_accounts_by_patient(
    patient_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: UserModel = Depends(get_current_user),
):
    # 🛡️ Validar pertenencia del paciente al tenant
    patient_check = (await db.execute(
        select(PatientModel.id).where(
            PatientModel.id == patient_id,
            PatientModel.tenant_id == current_user.tenant_id
        )
    )).scalar_one_or_none()
    if not patient_check:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Paciente no encontrado en esta clínica."
        )

    query = (
        select(AccountReceivable)
        .where(
            AccountReceivable.patient_id == patient_id,
            AccountReceivable.tenant_id == current_user.tenant_id,
        )
        .options(selectinload(AccountReceivable.payments))
        .order_by(AccountReceivable.created_at.desc())
    )
    result = await db.execute(query)
    accounts = result.scalars().all()
    return await _attach_patients(db, accounts, current_user.tenant_id)


# 💰 4. REGISTRAR UN PAGO Y DESCONTAR SALDO
@router.post("/accounts/{account_id}/payments", response_model=PaymentResponse, status_code=status.HTTP_201_CREATED)
async def create_payment(
    account_id: UUID,
    payment: PaymentCreate,
    db: AsyncSession = Depends(get_db),
    current_user: UserModel = Depends(require_role(["ADMIN", "RECEPTIONIST"])),
):
    query = select(AccountReceivable).where(
        AccountReceivable.id == account_id,
        AccountReceivable.tenant_id == current_user.tenant_id,
    )
    result = await db.execute(query)
    db_account = result.scalar_one_or_none()

    if not db_account:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Cuenta no encontrada en esta clínica."
        )

    if db_account.status == "PAID":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Esta cuenta ya fue saldada por completo."
        )

    if payment.amount_paid > db_account.balance_due:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"El abono ({payment.amount_paid}) supera el saldo pendiente ({db_account.balance_due})"
        )

    payment_data = payment.model_dump()
    payment_data["account_id"] = account_id
    payment_data["tenant_id"] = current_user.tenant_id
    payment_data["created_by"] = current_user.id

    db_payment = Payment(**payment_data)
    db.add(db_payment)

    db_account.balance_due -= payment.amount_paid
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

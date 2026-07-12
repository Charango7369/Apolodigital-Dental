# app/modules/dashboard/router.py
from datetime import datetime, timezone
from typing import List, Optional
from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy import func

from app.db.session import get_db
from app.modules.auth.dependencies import get_current_user
from app.modules.users.models import User as UserModel
from app.modules.patients.models import Patient as PatientModel
from app.modules.appointments.models import Appointment as AppointmentModel
from app.modules.billing.models import AccountReceivable, Payment

router = APIRouter(prefix="/dashboard", tags=["Dashboard"])


# ─── Schemas de respuesta ─────────────────────────────────────────────────────

class UpcomingAppointment(BaseModel):
    id: str
    patient_id: str
    start_time: str
    status: str
    reason: Optional[str] = None


class DashboardSummary(BaseModel):
    total_patients: int
    appointments_today: int
    pending_today: int
    pending_accounts: int
    total_balance_due: float
    monthly_income: float
    new_patients_month: int
    upcoming_appointments: List[UpcomingAppointment]
    generated_at: str


# ─── Endpoint ─────────────────────────────────────────────────────────────────

@router.get("/summary", response_model=DashboardSummary)
async def get_dashboard_summary(
    db: AsyncSession = Depends(get_db),
    current_user: UserModel = Depends(get_current_user),
):
    tenant_id = current_user.tenant_id
    now = datetime.now(timezone.utc)

    start_of_day   = now.replace(hour=0,  minute=0,  second=0,  microsecond=0)
    end_of_day     = now.replace(hour=23, minute=59, second=59, microsecond=999999)
    start_of_month = now.replace(day=1,   hour=0,    minute=0,  second=0, microsecond=0)

    # 1. Total pacientes activos
    r = await db.execute(
        select(func.count(PatientModel.id)).where(
            PatientModel.tenant_id == tenant_id,
            PatientModel.is_active == True,
        )
    )
    total_patients = r.scalar() or 0

    # 2. Citas de hoy
    r = await db.execute(
        select(func.count(AppointmentModel.id)).where(
            AppointmentModel.tenant_id == tenant_id,
            AppointmentModel.is_active == True,
            AppointmentModel.start_time >= start_of_day,
            AppointmentModel.start_time <= end_of_day,
        )
    )
    appointments_today = r.scalar() or 0

    # 3. Citas pendientes/confirmadas hoy
    r = await db.execute(
        select(func.count(AppointmentModel.id)).where(
            AppointmentModel.tenant_id == tenant_id,
            AppointmentModel.is_active == True,
            AppointmentModel.start_time >= start_of_day,
            AppointmentModel.start_time <= end_of_day,
            AppointmentModel.status.in_(["PENDING", "CONFIRMED"]),
        )
    )
    pending_today = r.scalar() or 0

    # 4. Cuentas por cobrar pendientes
    r = await db.execute(
        select(func.count(AccountReceivable.id)).where(
            AccountReceivable.tenant_id == tenant_id,
            AccountReceivable.is_active == True,
            AccountReceivable.status.in_(["PENDING", "PARTIAL"]),
        )
    )
    pending_accounts = r.scalar() or 0

    # 5. Saldo total pendiente (Bs.)
    r = await db.execute(
        select(func.coalesce(func.sum(AccountReceivable.balance_due), 0)).where(
            AccountReceivable.tenant_id == tenant_id,
            AccountReceivable.is_active == True,
            AccountReceivable.status.in_(["PENDING", "PARTIAL"]),
        )
    )
    total_balance_due = float(r.scalar() or 0)

    # 6. Ingresos del mes (pagos registrados)
    r = await db.execute(
        select(func.coalesce(func.sum(Payment.amount_paid), 0)).where(
            Payment.tenant_id == tenant_id,
            Payment.is_active == True,
            Payment.created_at >= start_of_month,
        )
    )
    monthly_income = float(r.scalar() or 0)

    # 7. Nuevos pacientes este mes
    r = await db.execute(
        select(func.count(PatientModel.id)).where(
            PatientModel.tenant_id == tenant_id,
            PatientModel.created_at >= start_of_month,
        )
    )
    new_patients_month = r.scalar() or 0

    # 8. Próximas 5 citas desde ahora
    r = await db.execute(
        select(AppointmentModel)
        .where(
            AppointmentModel.tenant_id == tenant_id,
            AppointmentModel.is_active == True,
            AppointmentModel.start_time >= now,
            AppointmentModel.status.in_(["PENDING", "CONFIRMED"]),
        )
        .order_by(AppointmentModel.start_time.asc())
        .limit(5)
    )
    upcoming_appointments = [
        UpcomingAppointment(
            id=str(apt.id),
            patient_id=str(apt.patient_id),
            start_time=apt.start_time.isoformat(),
            status=apt.status,
            reason=apt.reason,
        )
        for apt in r.scalars().all()
    ]

    return DashboardSummary(
        total_patients=total_patients,
        appointments_today=appointments_today,
        pending_today=pending_today,
        pending_accounts=pending_accounts,
        total_balance_due=total_balance_due,
        monthly_income=monthly_income,
        new_patients_month=new_patients_month,
        upcoming_appointments=upcoming_appointments,
        generated_at=now.isoformat(),
    )
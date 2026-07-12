# app/modules/reports/router.py
from datetime import datetime, timezone, timedelta
from typing import List, Optional
from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy import func, text

from app.db.session import get_db
from app.modules.auth.dependencies import get_current_user
from app.modules.users.models import User as UserModel
from app.modules.billing.models import Payment

router = APIRouter(prefix="/reports", tags=["Reports"])


# ─── Schemas ──────────────────────────────────────────────────────────────────

class IncomePeriodPoint(BaseModel):
    period: str    # etiqueta de fecha (ISO) truncada según granularidad
    total: float
    count: int

class MethodBreakdown(BaseModel):
    method: str
    total: float
    count: int

class IncomeReportResponse(BaseModel):
    granularity: str
    start_date: str
    end_date: str
    total_income: float
    total_payments: int
    average_per_period: float
    series: List[IncomePeriodPoint]
    by_method: List[MethodBreakdown]


# Límite de puntos para evitar gráficos con miles de barras
MAX_POINTS = 366

INTERVAL_BY_GRANULARITY = {
    "day": "1 day",
    "week": "1 week",
    "month": "1 month",
}


# ─── Endpoint: Ingresos por período ────────────────────────────────────────────

@router.get("/income", response_model=IncomeReportResponse)
async def get_income_report(
    granularity: str = Query("day", pattern="^(day|week|month)$"),
    start_date: Optional[datetime] = Query(None),
    end_date: Optional[datetime] = Query(None),
    db: AsyncSession = Depends(get_db),
    current_user: UserModel = Depends(get_current_user),
):
    now = datetime.now(timezone.utc)

    # Rangos por defecto según granularidad si no se especifican
    if not end_date:
        end_date = now
    if not start_date:
        if granularity == "day":
            start_date = end_date - timedelta(days=30)
        elif granularity == "week":
            start_date = end_date - timedelta(weeks=12)
        else:  # month
            start_date = end_date - timedelta(days=365)

    # 🚨 Salvaguarda: si el rango es demasiado amplio para la granularidad
    # elegida (ej. 5 años en modo diario), lo acortamos para no generar
    # miles de barras.
    max_span = {
        "day": timedelta(days=MAX_POINTS),
        "week": timedelta(weeks=MAX_POINTS),
        "month": timedelta(days=MAX_POINTS * 31),
    }[granularity]
    if (end_date - start_date) > max_span:
        start_date = end_date - max_span

    interval = INTERVAL_BY_GRANULARITY[granularity]

    # ── Serie temporal COMPLETA (rellena períodos sin pagos con 0) ──────────
    # generate_series crea un punto por cada día/semana/mes del rango, y el
    # LEFT JOIN trae el total real donde exista; donde no haya pagos, COALESCE
    # devuelve 0. Así el gráfico refleja proporcionalmente todo el rango,
    # en vez de solo los períodos donde hubo actividad.
    series_sql = text(f"""
        SELECT
            gs.period AS period,
            COALESCE(SUM(p.amount_paid), 0) AS total,
            COUNT(p.id) AS count
        FROM generate_series(
            date_trunc(:granularity, CAST(:start_date AS timestamptz)),
            date_trunc(:granularity, CAST(:end_date AS timestamptz)),
            CAST(:interval AS interval)
        ) AS gs(period)
        LEFT JOIN payments p
            ON date_trunc(:granularity, p.created_at) = gs.period
            AND p.tenant_id = :tenant_id
            AND p.is_active = true
            AND p.created_at >= :start_date
            AND p.created_at <= :end_date
        GROUP BY gs.period
        ORDER BY gs.period
    """)

    series_result = await db.execute(
        series_sql,
        {
            "granularity": granularity,
            "start_date": start_date,
            "end_date": end_date,
            "interval": interval,
            "tenant_id": current_user.tenant_id,
        },
    )
    series = [
        IncomePeriodPoint(
            period=row.period.isoformat(),
            total=float(row.total),
            count=row.count,
        )
        for row in series_result.all()
    ]

    # ── Totales generales del rango (sobre datos reales, no la serie rellena) ─
    totals_query = select(
        func.coalesce(func.sum(Payment.amount_paid), 0),
        func.count(Payment.id),
    ).where(
        Payment.tenant_id == current_user.tenant_id,
        Payment.is_active == True,
        Payment.created_at >= start_date,
        Payment.created_at <= end_date,
    )
    totals_result = await db.execute(totals_query)
    total_income, total_payments = totals_result.one()
    total_income = float(total_income)

    # El promedio se calcula sobre el total de períodos (incluye los que están en 0)
    average_per_period = total_income / len(series) if series else 0.0

    # ── Desglose por método de pago ──────────────────────────────────────────
    method_query = (
        select(
            Payment.payment_method,
            func.coalesce(func.sum(Payment.amount_paid), 0).label("total"),
            func.count(Payment.id).label("count"),
        )
        .where(
            Payment.tenant_id == current_user.tenant_id,
            Payment.is_active == True,
            Payment.created_at >= start_date,
            Payment.created_at <= end_date,
        )
        .group_by(Payment.payment_method)
        .order_by(func.sum(Payment.amount_paid).desc())
    )
    method_result = await db.execute(method_query)
    by_method = [
        MethodBreakdown(method=row.payment_method, total=float(row.total), count=row.count)
        for row in method_result.all()
    ]

    return IncomeReportResponse(
        granularity=granularity,
        start_date=start_date.isoformat(),
        end_date=end_date.isoformat(),
        total_income=total_income,
        total_payments=total_payments,
        average_per_period=average_per_period,
        series=series,
        by_method=by_method,
    )
    
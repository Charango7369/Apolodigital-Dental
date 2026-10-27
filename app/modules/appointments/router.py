import traceback
from datetime import datetime, timezone
from uuid import UUID
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, status, BackgroundTasks, Query, Response
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy import and_, or_, func
from sqlalchemy.orm import joinedload

from app.db.session import get_db
from app.modules.appointments.models import Appointment as AppointmentModel
from app.modules.appointments.schemas import (
    AppointmentCreate,
    AppointmentResponse,
    AppointmentUpdate,
    AppointmentRescheduleRequest,
    AppointmentCompleteRequest,
    AppointmentMetricsToday,
)
from app.modules.auth.dependencies import get_current_user
from app.modules.users.models import User as UserModel
from app.modules.patients.models import Patient as PatientModel
from app.services.whatsapp_service import wa_service
from app.services.whatsapp_cloud import whatsapp_cloud
from app.modules.billing.models import AccountReceivable

router = APIRouter(prefix="/appointments", tags=["Appointments"])

# ➕ 1. AGENDAR CITA (Con validación atómica de solapamientos)
@router.post("", response_model=AppointmentResponse, status_code=status.HTTP_201_CREATED)
async def create_appointment(
    payload: AppointmentCreate,
    db: AsyncSession = Depends(get_db),
    current_user: UserModel = Depends(get_current_user)
):
    try:
        ahora = datetime.now(timezone.utc)

        # 🛡️ ALGORITMO ANTI-SOLAPAMIENTO
        overlap_query = select(AppointmentModel).where(
            and_(
                AppointmentModel.tenant_id == current_user.tenant_id,
                AppointmentModel.doctor_id == payload.doctor_id,
                AppointmentModel.is_active == True,
                AppointmentModel.status.in_(["PENDING", "CONFIRMED"]),
                AppointmentModel.start_time < payload.end_time,
                AppointmentModel.end_time > payload.start_time
            )
        )

        overlap_result = await db.execute(overlap_query)
        existing_overlap = overlap_result.scalars().first()

        if existing_overlap:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="El doctor ya tiene una cita agendada o pendiente en ese rango de horario."
            )

        new_appointment = AppointmentModel(
            **payload.model_dump(),
            status="PENDING",
            tenant_id=current_user.tenant_id,
            is_active=True,
            created_at=ahora,
            updated_at=ahora
        )

        db.add(new_appointment)
        await db.flush()
        safe_appointment_id = new_appointment.id
        await db.commit()

        query = select(AppointmentModel).options(
            joinedload(AppointmentModel.patient),
            joinedload(AppointmentModel.doctor)
        ).where(
            AppointmentModel.id == safe_appointment_id
        )
        result = await db.execute(query)
        appointment_with_relations = result.scalar_one()

        return appointment_with_relations

    except Exception as e:
        await db.rollback()
        print("\n❌ ====== ¡FALLO EN AGENDAMIENTO DE CITA! ====== ❌")
        traceback.print_exc()
        if isinstance(e, HTTPException):
            raise e
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Error al procesar la cita: {str(e)}"
        )

# 📊 2. MÉTRICAS DEL DÍA PARA EL DASHBOARD LATERAL (Citas, Pacientes atendidos, Cobros estimados)
@router.get("/metrics/today", response_model=AppointmentMetricsToday)
async def get_today_appointment_metrics(
    db: AsyncSession = Depends(get_db),
    current_user: UserModel = Depends(get_current_user)
):
    now = datetime.now(timezone.utc)
    start_of_day = now.replace(hour=0, minute=0, second=0, microsecond=0)
    end_of_day = now.replace(hour=23, minute=59, second=59, microsecond=999999)

    # 1. Total del día
    base_query = select(AppointmentModel).where(
        and_(
            AppointmentModel.tenant_id == current_user.tenant_id,
            AppointmentModel.is_active == True,
            AppointmentModel.start_time >= start_of_day,
            AppointmentModel.start_time <= end_of_day
        )
    )
    result = await db.execute(base_query)
    today_apts = result.scalars().all()

    total = len(today_apts)
    attended = sum(1 for a in today_apts if a.status == "COMPLETED")
    pending = sum(1 for a in today_apts if a.status == "PENDING")
    confirmed = sum(1 for a in today_apts if a.status == "CONFIRMED")
    cancelled = sum(1 for a in today_apts if a.status in ["CANCELLED", "NO_SHOW"])

    # 2. Ingreso estimado / cobrado hoy a través de cuentas por cobrar
    billing_query = select(func.coalesce(func.sum(AccountReceivable.total_amount), 0)).where(
        and_(
            AccountReceivable.tenant_id == current_user.tenant_id,
            AccountReceivable.is_active == True,
            AccountReceivable.created_at >= start_of_day,
            AccountReceivable.created_at <= end_of_day
        )
    )
    billing_result = await db.execute(billing_query)
    estimated_income = float(billing_result.scalar() or 0.0)

    return AppointmentMetricsToday(
        total_today=total,
        attended_today=attended,
        pending_today=pending,
        confirmed_today=confirmed,
        cancelled_today=cancelled,
        estimated_income_today=estimated_income
    )

# 🔍 3. OBTENER AGENDA DE LA CLÍNICA (Filtros por Fecha, Doctor, Paciente, Estado y Búsqueda Libre)
@router.get("", response_model=List[AppointmentResponse])
async def get_my_clinic_agenda(
    start_date: Optional[datetime] = Query(None, description="Límite inferior UTC"),
    end_date: Optional[datetime] = Query(None, description="Límite superior UTC"),
    patient_id: Optional[UUID] = Query(None, description="Filtrar por paciente específico"),
    doctor_id: Optional[UUID] = Query(None, description="Filtrar por odontólogo asignado"),
    status: Optional[str] = Query(None, description="Filtrar por estado"),
    search: Optional[str] = Query(None, description="Buscar por nombre de paciente o motivo"),
    db: AsyncSession = Depends(get_db),
    current_user: UserModel = Depends(get_current_user)
):
    base_conditions = [
        AppointmentModel.tenant_id == current_user.tenant_id,
        AppointmentModel.is_active == True
    ]

    if start_date:
        base_conditions.append(AppointmentModel.start_time >= start_date)
    if end_date:
        base_conditions.append(AppointmentModel.start_time <= end_date)
    if patient_id:
        base_conditions.append(AppointmentModel.patient_id == patient_id)
    if doctor_id:
        base_conditions.append(AppointmentModel.doctor_id == doctor_id)
    if status:
        base_conditions.append(AppointmentModel.status == status)

    query = select(AppointmentModel).options(
        joinedload(AppointmentModel.patient),
        joinedload(AppointmentModel.doctor)
    ).where(and_(*base_conditions))

    if search and search.strip():
        term = f"%{search.strip()}%"
        query = query.join(AppointmentModel.patient).where(
            or_(
                PatientModel.first_name.ilike(term),
                PatientModel.last_name.ilike(term),
                AppointmentModel.reason.ilike(term)
            )
        )

    # Orden cronológico natural para visualización de agenda
    query = query.order_by(AppointmentModel.start_time.asc())

    result = await db.execute(query)
    appointments = result.scalars().all()

    return [AppointmentResponse.model_validate(appt) for appt in appointments]

# 🔀 4. REAGENDAR CITA (Drag & Drop específico con validación de colisiones)
@router.patch("/{appointment_id}/reschedule", response_model=AppointmentResponse)
async def reschedule_appointment(
    appointment_id: UUID,
    payload: AppointmentRescheduleRequest,
    db: AsyncSession = Depends(get_db),
    current_user: UserModel = Depends(get_current_user)
):
    query = select(AppointmentModel).where(
        AppointmentModel.id == appointment_id,
        AppointmentModel.tenant_id == current_user.tenant_id
    )
    result = await db.execute(query)
    appointment = result.scalar_one_or_none()

    if not appointment:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Cita no encontrada.")

    # 🛡️ Validar que el doctor no tenga otra cita solapada
    overlap_query = select(AppointmentModel).where(
        and_(
            AppointmentModel.tenant_id == current_user.tenant_id,
            AppointmentModel.doctor_id == appointment.doctor_id,
            AppointmentModel.id != appointment_id,
            AppointmentModel.is_active == True,
            AppointmentModel.status.in_(["PENDING", "CONFIRMED"]),
            AppointmentModel.start_time < payload.end_time,
            AppointmentModel.end_time > payload.start_time
        )
    )
    overlap_result = await db.execute(overlap_query)
    if overlap_result.scalars().first():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="El doctor ya tiene otra cita en el horario seleccionado."
        )

    appointment.start_time = payload.start_time
    appointment.end_time = payload.end_time
    appointment.updated_at = datetime.now(timezone.utc)
    await db.commit()

    query_with_relations = select(AppointmentModel).options(
        joinedload(AppointmentModel.patient),
        joinedload(AppointmentModel.doctor)
    ).where(AppointmentModel.id == appointment_id)
    res = await db.execute(query_with_relations)
    return res.scalar_one()

# 🔄 5. MODIFICAR ESTADO O DETALLES GENERALES
@router.patch("/{appointment_id}", response_model=AppointmentResponse)
async def update_appointment(
    appointment_id: UUID,
    payload: AppointmentUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: UserModel = Depends(get_current_user)
):
    query = select(AppointmentModel).where(
        AppointmentModel.id == appointment_id,
        AppointmentModel.tenant_id == current_user.tenant_id
    )
    result = await db.execute(query)
    appointment = result.scalar_one_or_none()

    if not appointment:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Cita no encontrada.")

    update_data = payload.model_dump(exclude_unset=True)

    # Si se actualizan fechas en el update general, verificar solapamiento
    new_start = update_data.get("start_time", appointment.start_time)
    new_end = update_data.get("end_time", appointment.end_time)
    if "start_time" in update_data or "end_time" in update_data:
        overlap_query = select(AppointmentModel).where(
            and_(
                AppointmentModel.tenant_id == current_user.tenant_id,
                AppointmentModel.doctor_id == appointment.doctor_id,
                AppointmentModel.id != appointment_id,
                AppointmentModel.is_active == True,
                AppointmentModel.status.in_(["PENDING", "CONFIRMED"]),
                AppointmentModel.start_time < new_end,
                AppointmentModel.end_time > new_start
            )
        )
        overlap_res = await db.execute(overlap_query)
        if overlap_res.scalars().first():
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="El doctor ya tiene una cita agendada o pendiente en ese rango de horario."
            )

    for key, value in update_data.items():
        setattr(appointment, key, value)

    appointment.updated_at = datetime.now(timezone.utc)
    await db.commit()

    query_with_relations = select(AppointmentModel).options(
        joinedload(AppointmentModel.patient),
        joinedload(AppointmentModel.doctor)
    ).where(AppointmentModel.id == appointment_id)
    result = await db.execute(query_with_relations)
    return result.scalar_one()

# 📲 6. ENVIAR RECORDATORIO POR WHATSAPP CLOUD API
@router.post("/{appointment_id}/send-reminder")
async def send_appointment_reminder_endpoint(
    appointment_id: UUID,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
    current_user: UserModel = Depends(get_current_user)
):
    query = select(AppointmentModel).options(
        joinedload(AppointmentModel.patient),
        joinedload(AppointmentModel.doctor)
    ).where(
        and_(
            AppointmentModel.id == appointment_id,
            AppointmentModel.tenant_id == current_user.tenant_id
        )
    )
    result = await db.execute(query)
    appointment = result.scalar_one_or_none()

    if not appointment:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Cita no encontrada.")

    if not appointment.patient or not appointment.patient.phone:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="El paciente no tiene un número telefónico registrado para WhatsApp."
        )

    patient_name = f"{appointment.patient.first_name} {appointment.patient.last_name}"
    date_str = appointment.start_time.strftime("%d/%m/%Y")
    time_str = appointment.start_time.strftime("%H:%M")

    # Enviar en segundo plano para latencia cero en la interfaz
    background_tasks.add_task(
        whatsapp_cloud.send_appointment_reminder,
        to_phone=appointment.patient.phone,
        patient_name=patient_name,
        date_str=date_str,
        time_str=time_str,
        clinic_name="ApoloDigital Dental"
    )

    return {"message": "Recordatorio de WhatsApp encolado exitosamente", "recipient": appointment.patient.phone}

# 📅 7. EXPORTACIÓN DE CALENDARIO RFC 5545 (.ICS PARA OUTLOOK / GOOGLE / APPLE)
@router.get("/{appointment_id}/ics")
async def export_appointment_ics(
    appointment_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: UserModel = Depends(get_current_user)
):
    query = select(AppointmentModel).options(
        joinedload(AppointmentModel.patient),
        joinedload(AppointmentModel.doctor)
    ).where(
        and_(
            AppointmentModel.id == appointment_id,
            AppointmentModel.tenant_id == current_user.tenant_id
        )
    )
    result = await db.execute(query)
    apt = result.scalar_one_or_none()

    if not apt:
        raise HTTPException(status_code=404, detail="Cita no encontrada.")

    patient_name = f"{apt.patient.first_name} {apt.patient.last_name}" if apt.patient else "Paciente"
    doctor_name = apt.doctor.full_name if apt.doctor else "Odontólogo"
    start_fmt = apt.start_time.strftime("%Y%m%dT%H%M%SZ")
    end_fmt = apt.end_time.strftime("%Y%m%dT%H%M%SZ")

    ics_content = (
        "BEGIN:VCALENDAR\r\n"
        "VERSION:2.0\r\n"
        "PRODID:-//ApoloDigital Dental SaaS//ES\r\n"
        "CALSCALE:GREGORIAN\r\n"
        "BEGIN:VEVENT\r\n"
        f"UID:{apt.id}@apolodigital.dental\r\n"
        f"DTSTAMP:{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}\r\n"
        f"DTSTART:{start_fmt}\r\n"
        f"DTEND:{end_fmt}\r\n"
        f"SUMMARY:Cita Dental: {patient_name}\r\n"
        f"DESCRIPTION:Atención con {doctor_name}. Motivo: {apt.reason or 'Consulta Odontológica'}\r\n"
        "STATUS:CONFIRMED\r\n"
        "END:VEVENT\r\n"
        "END:VCALENDAR\r\n"
    )

    return Response(
        content=ics_content,
        media_type="text/calendar",
        headers={"Content-Disposition": f"attachment; filename=cita_{apt.id}.ics"}
    )

# 🏁 8. FINALIZAR CITA, GENERAR COBRO Y ENVIAR WHATSAPP (Unificado)
@router.post("/{appointment_id}/complete", status_code=status.HTTP_200_OK)
async def complete_appointment_and_bill(
    appointment_id: UUID,
    payload: AppointmentCompleteRequest,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
    current_user: UserModel = Depends(get_current_user)
):
    query = select(AppointmentModel).options(
        joinedload(AppointmentModel.patient),
        joinedload(AppointmentModel.doctor)
    ).where(
        and_(
            AppointmentModel.id == appointment_id,
            AppointmentModel.tenant_id == current_user.tenant_id
        )
    )
    result = await db.execute(query)
    db_appointment = result.scalar_one_or_none()

    if not db_appointment:
        raise HTTPException(status_code=404, detail="Cita no encontrada en esta clínica.")

    if db_appointment.status == "COMPLETED":
        raise HTTPException(status_code=400, detail="Esta cita ya fue completada y facturada.")

    ahora = datetime.now(timezone.utc)

    # 1. Actualizamos estado de la cita
    db_appointment.status = "COMPLETED"
    db_appointment.updated_at = ahora

    # 2. Creamos la deuda (Cuenta por Cobrar)
    new_account = AccountReceivable(
        patient_id=db_appointment.patient_id,
        tenant_id=current_user.tenant_id,
        total_amount=payload.final_cost,
        balance_due=payload.final_cost,
        status="PENDING",
        description=f"Tratamiento completado - Cita del {db_appointment.start_time.strftime('%Y-%m-%d')}: {payload.treatment_description}",
        is_active=True,
        created_at=ahora,
        updated_at=ahora
    )

    db.add(new_account)

    # ── Parte crítica: commit de cita + cuenta ──────────────────────────────
    try:
        await db.commit()
        await db.refresh(db_appointment)
        await db.refresh(new_account)
    except Exception as e:
        await db.rollback()
        print("\n❌ ====== ¡FALLO AL FINALIZAR CITA Y FACTURAR! ====== ❌")
        traceback.print_exc()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Error en la transacción: {str(e)}"
        )

    # ── Parte no crítica: notificación WhatsApp (best-effort) ───────────────
    try:
        if db_appointment.patient and db_appointment.patient.phone:
            patient_phone = db_appointment.patient.phone
            mensaje_ws = (
                f"¡Hola {db_appointment.patient.first_name}! Esperamos que te sientas muy bien tras tu consulta dental hoy. 🦷\n\n"
                f"El total de tu tratamiento fue de *Bs. {payload.final_cost}*. "
                f"Cualquier duda, estamos a tu disposición."
            )

            background_tasks.add_task(
                whatsapp_cloud.send_text_message,
                to_phone=patient_phone,
                text=mensaje_ws
            )
    except Exception:
        print("\n⚠️ ====== AVISO: No se pudo encolar WhatsApp ====== ⚠️")
        traceback.print_exc()

    return {
        "message": "Cita completada y cuenta por cobrar generada exitosamente",
        "appointment_id": db_appointment.id,
        "account_id": new_account.id
    }

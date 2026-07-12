import traceback
from datetime import datetime, timezone
from uuid import UUID
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, status, BackgroundTasks, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy import and_
from sqlalchemy.orm import joinedload

from app.db.session import get_db
from app.modules.appointments.models import Appointment as AppointmentModel
from app.modules.appointments.schemas import (
    AppointmentCreate,
    AppointmentResponse,
    AppointmentUpdate,
    AppointmentCompleteRequest
)
from app.modules.auth.dependencies import get_current_user
from app.modules.users.models import User as UserModel
from app.modules.patients.models import Patient as PatientModel
from app.services.whatsapp_service import wa_service
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

        query = select(AppointmentModel).options(joinedload(AppointmentModel.patient)).where(
            AppointmentModel.id == safe_appointment_id
        )
        result = await db.execute(query)
        appointment_with_patient = result.scalar_one()

        return appointment_with_patient

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

# 🔍 2. OBTENER AGENDA DE LA CLÍNICA (Protegido con rango de fechas y paciente opcional)
@router.get("", response_model=List[AppointmentResponse])
async def get_my_clinic_agenda(
    start_date: Optional[datetime] = Query(None, description="Límite inferior UTC"),
    end_date: Optional[datetime] = Query(None, description="Límite superior UTC"),
    patient_id: Optional[UUID] = Query(None, description="Filtrar por paciente específico"),
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

    query = select(AppointmentModel).options(joinedload(AppointmentModel.patient)).where(and_(*base_conditions)).order_by(AppointmentModel.start_time.desc())

    result = await db.execute(query)
    appointments = result.scalars().all()

    return [AppointmentResponse.model_validate(appt) for appt in appointments]

# 🔄 3. MODIFICAR ESTADO O REAGENDAR CITA
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
    for key, value in update_data.items():
        setattr(appointment, key, value)

    appointment.updated_at = datetime.now(timezone.utc)
    await db.commit()

    # 🚨 Re-consulta con joinedload para incluir datos del paciente en la respuesta
    query_with_patient = select(AppointmentModel).options(
        joinedload(AppointmentModel.patient)
    ).where(AppointmentModel.id == appointment_id)
    result = await db.execute(query_with_patient)
    return result.scalar_one()

# 🏁 4. FINALIZAR CITA, GENERAR COBRO Y ENVIAR WHATSAPP (Unificado)
@router.post("/{appointment_id}/complete", status_code=status.HTTP_200_OK)
async def complete_appointment_and_bill(
    appointment_id: UUID,
    payload: AppointmentCompleteRequest,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
    current_user: UserModel = Depends(get_current_user)
):
    query = select(AppointmentModel).options(joinedload(AppointmentModel.patient)).where(
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
    # Si esto falla, sí queremos hacer rollback (son los datos importantes).
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
    # 🚨 FIX: WhatsAppService aún es un mock en desarrollo (no tiene send_message).
    # Este bloque NUNCA debe tumbar la respuesta exitosa de facturación.
    try:
        if db_appointment.patient and db_appointment.patient.phone and hasattr(wa_service, "send_message"):
            patient_phone = db_appointment.patient.phone
            instance_name = str(current_user.tenant_id)

            mensaje_ws = (
                f"¡Hola {db_appointment.patient.first_name}! Esperamos que te sientas muy bien tras tu consulta dental hoy. 🦷\n\n"
                f"El total de tu tratamiento fue de *Bs. {payload.final_cost}*. "
                f"Cualquier duda, estamos a tu disposición."
            )

            background_tasks.add_task(
                wa_service.send_message,
                instance_name=instance_name,
                phone=patient_phone,
                text=mensaje_ws
            )
    except Exception:
        # No interrumpe la respuesta: solo lo dejamos registrado en logs.
        print("\n⚠️ ====== AVISO: No se pudo notificar por WhatsApp (no crítico) ====== ⚠️")
        traceback.print_exc()

    return {
        "message": "Cita completada y cuenta por cobrar generada exitosamente",
        "appointment_id": db_appointment.id,
        "account_id": new_account.id
    }
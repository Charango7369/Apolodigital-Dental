import traceback
from datetime import datetime, timezone
from uuid import UUID
from typing import List

from fastapi import APIRouter, Depends, HTTPException, status, BackgroundTasks
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy import and_

from app.db.session import get_db
from app.modules.appointments.models import Appointment as AppointmentModel
# 💡 IMPORTANTE: Asegúrate de haber agregado AppointmentCompleteRequest en schemas.py
from app.modules.appointments.schemas import AppointmentCreate, AppointmentResponse, AppointmentUpdate, AppointmentCompleteRequest
from app.modules.auth.dependencies import get_current_user
from app.modules.users.models import User as UserModel
from app.services.whatsapp_service import wa_service

# 💡 IMPORTAMOS EL MODELO FINANCIERO
from app.modules.billing.models import AccountReceivable

router = APIRouter(prefix="/appointments", tags=["Appointments"])

# ➕ 1. AGENDAR CITA (Con validación atómica de solapamientos)
@router.post("/", response_model=AppointmentResponse, status_code=status.HTTP_201_CREATED)
async def create_appointment(
    payload: AppointmentCreate, 
    db: AsyncSession = Depends(get_db),
    current_user: UserModel = Depends(get_current_user)
):
    try:
        ahora = datetime.now(timezone.utc)

        # 🛡️ ALGORITMO ANTI-SOLAPAMIENTO (Double-Booking Protection)
        # Una cita se cruza si: Start1 < End2 AND End1 > Start2
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
        existing_overlap = overlap_result.scalar_one_or_none()
        
        if existing_overlap:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="El doctor ya tiene una cita agendada o pendiente en ese rango de horario."
            )

        # Si el horario está libre, procedemos con la inserción imperativa
        new_appointment = AppointmentModel(
            patient_id=payload.patient_id,
            doctor_id=payload.doctor_id,
            start_time=payload.start_time,
            end_time=payload.end_time,
            reason=payload.reason,
            status="PENDING"
        )
        
        new_appointment.tenant_id = current_user.tenant_id
        new_appointment.created_by = current_user.id
        new_appointment.is_active = True
        new_appointment.created_at = ahora
        new_appointment.updated_at = ahora

        db.add(new_appointment)
        await db.commit()
        await db.refresh(new_appointment)
        return new_appointment

    except Exception as e:
        print("\n❌ ====== ¡FALLO EN AGENDAMIENTO DE CITA! ====== ❌")
        traceback.print_exc()
        print("❌ =================================================== \n")
        if isinstance(e, HTTPException):
            raise e
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, 
            detail=f"Error al procesar la cita: {str(e)}"
        )

# 🔍 2. OBTENER AGENDA DE LA CLÍNICA (Filtro Multi-Tenant)
@router.get("/", response_model=List[AppointmentResponse])
async def get_my_clinic_agenda(
    db: AsyncSession = Depends(get_db),
    current_user: UserModel = Depends(get_current_user)
):
    query = select(AppointmentModel).where(
        AppointmentModel.tenant_id == current_user.tenant_id
    ).order_by(AppointmentModel.start_time.asc())
    
    result = await db.execute(query)
    return result.scalars().all()

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
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, 
            detail="Cita no encontrada en esta clínica."
        )
    
    update_data = payload.model_dump(exclude_unset=True)
    
    for key, value in update_data.items():
        setattr(appointment, key, value)
        
    appointment.updated_at = datetime.now(timezone.utc)
    appointment.updated_by = current_user.id
    
    await db.commit()
    await db.refresh(appointment)
    return appointment


# 🏁 4. FINALIZAR CITA Y GENERAR COBRO (NUEVO)
@router.post("/{appointment_id}/complete", status_code=status.HTTP_200_OK)
async def complete_appointment_and_bill(
    appointment_id: UUID,
    payload: AppointmentCompleteRequest,
    db: AsyncSession = Depends(get_db),
    current_user: UserModel = Depends(get_current_user)
):
    query = select(AppointmentModel).where(
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

    # Actualizamos estado de la cita
    db_appointment.status = "COMPLETED"
    db_appointment.updated_at = ahora
    db_appointment.updated_by = current_user.id

    # Creamos la deuda vinculada a la auditoría del usuario actual
    new_account = AccountReceivable(
        patient_id=db_appointment.patient_id,
        total_amount=payload.final_cost,
        balance_due=payload.final_cost,
        status="PENDING",
        description=f"Tratamiento completado - Cita del {db_appointment.start_time.strftime('%Y-%m-%d')}: {payload.treatment_description}"
    )
    
    new_account.tenant_id = current_user.tenant_id
    new_account.created_by = current_user.id
    new_account.is_active = True
    new_account.created_at = ahora
    new_account.updated_at = ahora

    db.add(new_account)

    try:
        await db.commit()
        await db.refresh(db_appointment)
        await db.refresh(new_account)
        
        return {
            "message": "Cita completada y cuenta por cobrar generada exitosamente",
            "appointment_id": db_appointment.id,
            "account_id": new_account.id
        }
    except Exception as e:
        await db.rollback()
        print("\n❌ ====== ¡FALLO AL FINALIZAR CITA Y FACTURAR! ====== ❌")
        traceback.print_exc()
        print("❌ =================================================== \n")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Error en la transacción: {str(e)}"
        )

@router.post("/{appointment_id}/complete", status_code=status.HTTP_200_OK)
async def complete_appointment_and_bill(
    appointment_id: UUID,
    payload: AppointmentCompleteRequest,
    background_tasks: BackgroundTasks, # 👈 INYECTAMOS BACKGROUND TASKS
    db: AsyncSession = Depends(get_db),
    current_user: UserModel = Depends(get_current_user)
):
    # ... (TODA TU LÓGICA ANTERIOR DE BUSCAR LA CITA Y CREAR LA CUENTA SE QUEDA IGUAL)
    # db_appointment = ...
    # new_account = AccountReceivable(...)
    # db.add(new_account)
    # await db.commit()

    # 💡 LA MAGIA DE LAS NOTIFICACIONES EN SEGUNDO PLANO
    # Preparamos el mensaje a enviar
    instance_name = str(current_user.tenant_id)
    # Idealmente, extraerías el teléfono de db_appointment.patient.phone
    patient_phone = "59177777777" 
    
    mensaje_ws = (
        f"¡Hola! Esperamos que te sientas muy bien tras tu consulta dental hoy. 🦷\n\n"
        f"El total de tu tratamiento fue de *{payload.final_cost}*. "
        f"Cualquier duda, estamos a tu disposición."
    )

    # 🚀 Delegamos la petición HTTP a la tarea de fondo. 
    # FastAPI devolverá el JSON al instante y luego ejecutará esta función.
    background_tasks.add_task(
        wa_service.send_message, 
        instance_name=instance_name, 
        phone=patient_phone, 
        text=mensaje_ws
    )

    return {
        "message": "Cita completada y cuenta por cobrar generada exitosamente",
        "appointment_id": db_appointment.id,
        "account_id": new_account.id # En este punto el JSON ya se envió al frontend
    }
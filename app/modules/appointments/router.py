# app/modules/appointments/router.py
import traceback
from datetime import datetime, timezone
from uuid import UUID
from typing import List

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy import and_

from app.db.session import get_db
from app.modules.appointments.models import Appointment as AppointmentModel
from app.modules.appointments.schemas import AppointmentCreate, AppointmentResponse, AppointmentUpdate
from app.modules.auth.dependencies import get_current_user
from app.modules.users.models import User as UserModel

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
# app/modules/notifications/router.py
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from uuid import UUID
from typing import List

from app.db.session import get_db
from app.modules.notifications.schemas import NotificationCreate, NotificationUpdate, NotificationResponse
from app.modules.notifications.models import Notification as NotificationModel

router = APIRouter(prefix="/notifications", tags=["Notifications"])

# ➕ 1. CREAR / ENVIAR UNA NOTIFICACIÓN
@router.post("/", response_model=NotificationResponse, status_code=status.HTTP_201_CREATED)
async def create_notification(notification: NotificationCreate, db: AsyncSession = Depends(get_db)):
    db_notification = NotificationModel(**notification.model_dump())
    db.add(db_notification)
    try:
        await db.commit()
        await db.refresh(db_notification)
        return db_notification
    except Exception as e:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Error al generar la notificación: {str(e)}"
        )

# 🔍 2. OBTENER LAS NOTIFICACIONES DE UN USUARIO ESPECÍFICO (Filtrado por Clínica)
@router.get("/user/{user_id}", response_model=List[NotificationResponse])
async def get_user_notifications(user_id: UUID, tenant_id: UUID, db: AsyncSession = Depends(get_db)):
    # 🚨 FILTRO DE SEGURIDAD: Coma `,` para concatenar los AND de forma limpia
    query = select(NotificationModel).where(
        NotificationModel.user_id == user_id,
        NotificationModel.tenant_id == tenant_id
    ).order_by(NotificationModel.created_at.desc()) # Las más recientes primero
    
    result = await db.execute(query)
    notifications = result.scalars().all()
    return notifications

# 📝 3. MARCAR NOTIFICACIÓN COMO LEÍDA
@router.put("/{notification_id}/read", response_model=NotificationResponse)
async def mark_as_read(notification_id: UUID, tenant_id: UUID, db: AsyncSession = Depends(get_db)):
    query = select(NotificationModel).where(
        NotificationModel.id == notification_id,
        NotificationModel.tenant_id == tenant_id
    )
    result = await db.execute(query)
    db_notification = result.scalar_one_or_none()
    
    if not db_notification:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Notificación no encontrada en esta clínica"
        )
    
    db_notification.is_read = True
    
    try:
        await db.commit()
        await db.refresh(db_notification)
        return db_notification
    except Exception as e:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Error al actualizar la notificación: {str(e)}"
        )
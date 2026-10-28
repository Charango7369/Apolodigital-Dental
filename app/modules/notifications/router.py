# app/modules/notifications/router.py
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from uuid import UUID
from typing import List

from app.db.session import get_db
from app.modules.auth.dependencies import get_current_user
from app.modules.users.models import User as UserModel
from app.modules.notifications.schemas import NotificationCreate, NotificationResponse
from app.modules.notifications.models import Notification as NotificationModel

router = APIRouter(prefix="/notifications", tags=["Notifications"])


# ➕ 1. CREAR / ENVIAR UNA NOTIFICACIÓN (Aislamiento de Tenant)
@router.post("/", response_model=NotificationResponse, status_code=status.HTTP_201_CREATED)
async def create_notification(
    notification: NotificationCreate,
    db: AsyncSession = Depends(get_db),
    current_user: UserModel = Depends(get_current_user)
):
    notif_data = notification.model_dump()
    # 🛡️ Forzar tenant_id del usuario en sesión
    notif_data["tenant_id"] = current_user.tenant_id

    # Si se especifica un destinatario diferente, validar que pertenezca a la misma clínica
    target_user_id = notif_data.get("user_id") or current_user.id
    target_user = (await db.execute(
        select(UserModel.id).where(
            UserModel.id == target_user_id,
            UserModel.tenant_id == current_user.tenant_id,
            UserModel.is_active == True
        )
    )).scalar_one_or_none()
    if not target_user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Usuario destinatario no pertenece a esta clínica."
        )

    notif_data["user_id"] = target_user_id

    db_notification = NotificationModel(**notif_data)
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


# 🔍 2. OBTENER MIS NOTIFICACIONES (Sesión Autenticada)
@router.get("", response_model=List[NotificationResponse])
@router.get("/me", response_model=List[NotificationResponse])
async def get_my_notifications(
    db: AsyncSession = Depends(get_db),
    current_user: UserModel = Depends(get_current_user)
):
    query = select(NotificationModel).where(
        NotificationModel.user_id == current_user.id,
        NotificationModel.tenant_id == current_user.tenant_id
    ).order_by(NotificationModel.created_at.desc())
    
    result = await db.execute(query)
    return result.scalars().all()


# 🔍 2b. OBTENER NOTIFICACIONES DE UN USUARIO ESPECÍFICO (Solo ADMIN de la clínica)
@router.get("/user/{user_id}", response_model=List[NotificationResponse])
async def get_user_notifications(
    user_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: UserModel = Depends(get_current_user)
):
    user_roles = current_user.roles if isinstance(current_user.roles, list) else []
    is_admin = "ADMIN" in user_roles or "SUPER_ADMIN" in user_roles

    if user_id != current_user.id and not is_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="No autorizado para consultar notificaciones de otros usuarios."
        )

    query = select(NotificationModel).where(
        NotificationModel.user_id == user_id,
        NotificationModel.tenant_id == current_user.tenant_id
    ).order_by(NotificationModel.created_at.desc())
    
    result = await db.execute(query)
    return result.scalars().all()


# 📝 3. MARCAR NOTIFICACIÓN COMO LEÍDA (Validación de pertenencia)
@router.put("/{notification_id}/read", response_model=NotificationResponse)
async def mark_as_read(
    notification_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: UserModel = Depends(get_current_user)
):
    query = select(NotificationModel).where(
        NotificationModel.id == notification_id,
        NotificationModel.tenant_id == current_user.tenant_id,
        NotificationModel.user_id == current_user.id
    )
    result = await db.execute(query)
    db_notification = result.scalar_one_or_none()
    
    if not db_notification:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Notificación no encontrada en esta clínica."
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

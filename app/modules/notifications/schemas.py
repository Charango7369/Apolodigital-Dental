# app/modules/notifications/schemas.py
from pydantic import BaseModel, Field
from uuid import UUID
from datetime import datetime
from typing import Optional

# Esquema base con los campos comunes
class NotificationBase(BaseModel):
    title: str = Field(..., max_length=255, description="Título de la alerta (ej. Stock Bajo)")
    message: str = Field(..., description="Cuerpo detallado de la notificación")
    is_read: bool = Field(default=False, description="Estado de lectura de la notificación")

# Esquema para crear una notificación (Se envía al usuario X de la clínica Y)
class NotificationCreate(NotificationBase):
    user_id: UUID
    tenant_id: UUID

# Esquema para marcar como leída (El frontend solo suele cambiar el estado de lectura)
class NotificationUpdate(BaseModel):
    is_read: bool

# Esquema de respuesta para el Frontend
class NotificationResponse(NotificationBase):
    id: UUID
    user_id: UUID
    tenant_id: UUID
    created_at: datetime

    model_config = {
        "from_attributes": True
    }
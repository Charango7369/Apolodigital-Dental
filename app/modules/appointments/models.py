# app/modules/appointments/models.py
import uuid
from sqlalchemy import String, Text, ForeignKey, DateTime
from sqlalchemy.orm import mapped_column, Mapped
from datetime import datetime

from app.db.base import Base
from app.db.mixins import TimestampMixin, AuditMixin, TenantMixin

class Appointment(Base, TimestampMixin, AuditMixin, TenantMixin):
    __tablename__ = "appointments"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    patient_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("patients.id", ondelete="CASCADE"))
    doctor_id: Mapped[uuid.UUID] = mapped_column(nullable=False)
    
    # Manejo estricto de tiempos (UTC forzado en el backend)
    start_time: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    end_time: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    
    # Estados: PENDING, CONFIRMED, COMPLETED, CANCELLED, NO_SHOW
    status: Mapped[str] = mapped_column(String(50), default="PENDING")
    reason: Mapped[str] = mapped_column(Text, nullable=True)
    
    is_active: Mapped[bool] = mapped_column(default=True)
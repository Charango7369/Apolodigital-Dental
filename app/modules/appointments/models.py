from datetime import datetime, timezone
import uuid
from sqlalchemy import Column, String, DateTime, ForeignKey, Boolean, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from app.db.base import Base

class Appointment(Base):
    __tablename__ = "appointments"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, index=True)
    tenant_id = Column(UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True)
    
    # Llaves Foráneas Estrictas (Ambas son obligatorias según tu AppointmentBase)
    patient_id = Column(UUID(as_uuid=True), ForeignKey("patients.id", ondelete="CASCADE"), nullable=False, index=True)
    doctor_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)

    # Intervalo de la Cita
    start_time = Column(DateTime(timezone=True), nullable=False, index=True)
    end_time = Column(DateTime(timezone=True), nullable=False)
    
    # Motivo de consulta (Opcional)
    reason = Column(Text, nullable=True)
    
    # Estado (Valores esperados: PENDING, CONFIRMED, COMPLETED, CANCELLED, NO_SHOW)
    status = Column(String(50), default="PENDING", nullable=False)
    
    # Soft Delete
    is_active = Column(Boolean, default=True, nullable=False)

    # Auditoría
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

    # Relaciones ORM para navegación fluida
    patient = relationship("Patient", backref="appointments")
    doctor = relationship("User", backref="appointments_as_doctor")
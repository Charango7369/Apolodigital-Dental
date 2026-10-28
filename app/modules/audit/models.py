# app/modules/audit/models.py
"""
Modelo de Bitácora de Auditoría Médica Inmutable (HIPAA Security Rule § 164.312(b)).
Registra cada evento de lectura, creación, actualización y eliminación de PHI
con trazabilidad de usuario, clínica, IP y agente de usuario.
"""
import uuid
from datetime import datetime, timezone
from sqlalchemy import String, DateTime, ForeignKey, JSON, text
from sqlalchemy.orm import mapped_column, Mapped, relationship
from app.db.base import Base


class MedicalAuditLog(Base):
    __tablename__ = "medical_audit_logs"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True
    )
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("tenants.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )

    # Acción auditada: READ, CREATE, UPDATE, DELETE, EXPORT
    action: Mapped[str] = mapped_column(String(50), nullable=False, index=True)

    # Tipo de entidad: ODONTOGRAM, PATIENT, CLINICAL_NOTE, APPOINTMENT
    resource_type: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    resource_id: Mapped[uuid.UUID | None] = mapped_column(nullable=True, index=True)
    patient_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("patients.id", ondelete="SET NULL"),
        nullable=True,
        index=True
    )

    # Marca temporal inmutable en UTC
    timestamp: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        server_default=text("NOW()"),
        nullable=False,
        index=True
    )

    # Metadatos forenses del cliente
    ip_address: Mapped[str | None] = mapped_column(String(45), nullable=True)
    user_agent: Mapped[str | None] = mapped_column(String(255), nullable=True)

    # Información complementaria estructurada (cambios, campos tocados)
    details: Mapped[dict | None] = mapped_column(JSON, nullable=True)

    # Relaciones
    user = relationship("User", foreign_keys=[user_id])
    tenant = relationship("Tenant", foreign_keys=[tenant_id])
    patient = relationship("Patient", foreign_keys=[patient_id])

# app/modules/patients/models.py
import uuid
from sqlalchemy import Column, Integer, String, ForeignKey, DateTime, Boolean
from sqlalchemy.dialects.postgresql import UUID  # <-- Importamos el tipo UUID de PostgreSQL
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.db.base import Base
from app.db.mixins import TimestampMixin, TenantMixin 

# Aplicamos herencia múltiple: Los Mixins inyectarán tenant_id, created_at y updated_at
class Patient(TimestampMixin, TenantMixin, Base):
    __tablename__ = "patients"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    first_name = Column(String(255), nullable=False)
    last_name = Column(String(255), nullable=False)
    email = Column(String, nullable=True)
    phone = Column(String(50), nullable=True)
    is_active = Column(Boolean, default=True)
    # Relación
    tenant = relationship("Tenant")
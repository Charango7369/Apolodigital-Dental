import uuid
from sqlalchemy import Column, String, Integer, ForeignKey, Boolean, DateTime, func
from sqlalchemy.dialects.postgresql import UUID
from app.db.base import Base

class OdontogramEntry(Base):
    __tablename__ = "odontogram_entries"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tooth_number = Column(Integer, nullable=False) # Número de pieza dental
    status_item = Column(String(100), nullable=False) # Ej. "caries", "corona", "ausente"
    notes = Column(String(500), nullable=True)
    
    # Relaciones clave
    patient_id = Column(UUID(as_uuid=True), ForeignKey("patients.id", ondelete="CASCADE"), nullable=False)
    tenant_id = Column(UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False)
    
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), default=func.now())
    updated_at = Column(DateTime(timezone=True), default=func.now(), onupdate=func.now())
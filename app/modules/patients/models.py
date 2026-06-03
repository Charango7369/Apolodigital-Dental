# app/modules/patients/models.py
import uuid
from sqlalchemy import Column, Integer, String, ForeignKey
from sqlalchemy.dialects.postgresql import UUID  # <-- Importamos el tipo UUID de PostgreSQL
from sqlalchemy.orm import relationship
from app.db.base import Base 

class Patient(Base):
    __tablename__ = "patients"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    # Cambiado de Integer a UUID para que coincida exactamente con tenants.id
    tenant_id = Column(UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False)
    
    first_name = Column(String, nullable=False)
    last_name = Column(String, nullable=False)
    email = Column(String, nullable=True)
    phone = Column(String, nullable=True)

    # Relación
    tenant = relationship("Tenant")
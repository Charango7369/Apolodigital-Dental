# app/modules/appointments/models.py
from sqlalchemy import Column, Integer, String, ForeignKey, DateTime
from sqlalchemy.orm import relationship
from app.db.base import Base # <-- Usa la misma ruta que te funcionó en patients

class Appointment(Base):
    __tablename__ = "appointments"

    id = Column(Integer, primary_key=True, index=True)
    tenant_id = Column(Integer, ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False)
    patient_id = Column(Integer, ForeignKey("patients.id", ondelete="CASCADE"), nullable=False)
    appointment_date = Column(DateTime, nullable=False)
    notes = Column(String, nullable=True)

    # Relaciones
    tenant = relationship("Tenant")
    patient = relationship("Patient")
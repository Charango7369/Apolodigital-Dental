# app/modules/odontograms/models.py
import uuid
from sqlalchemy import String, Text, ForeignKey, JSON
from sqlalchemy.orm import mapped_column, Mapped

from app.db.base import Base
from app.db.mixins import TimestampMixin, AuditMixin, TenantMixin

class Odontogram(Base, TimestampMixin, AuditMixin, TenantMixin):
    __tablename__ = "odontograms"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    patient_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("patients.id", ondelete="CASCADE"))
    doctor_id: Mapped[uuid.UUID] = mapped_column(nullable=False)  # El doctor que realiza el registro
    description: Mapped[str] = mapped_column(Text, nullable=True)
    
    # Aquí se guarda el mapa de los dientes con sus estados y caras afectadas
    teeth_data: Mapped[dict] = mapped_column(JSON, default=dict, server_default=" '{}'::jsonb ")
    is_active: Mapped[bool] = mapped_column(default=True)
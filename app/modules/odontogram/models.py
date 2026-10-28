# app/modules/odontogram/models.py
import uuid
from sqlalchemy import String, Text, ForeignKey, text
from sqlalchemy.orm import mapped_column, Mapped

from app.db.base import Base
from app.db.mixins import TimestampMixin, AuditMixin, TenantMixin
from app.core.encryption import EncryptedJSON


class Odontogram(Base, TimestampMixin, AuditMixin, TenantMixin):
    __tablename__ = "odontograms"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    patient_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("patients.id", ondelete="CASCADE"))
    doctor_id: Mapped[uuid.UUID] = mapped_column(nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=True)
    
    # 🔐 FASE 4: Cifrado autenticado AES-256-GCM a nivel de campo (HIPAA / GDPR)
    # En la base de datos se persiste cifrado con Nonce único por registro.
    # En la aplicación se accede y manipula transparentemente como diccionario.
    teeth_data: Mapped[dict] = mapped_column(
        EncryptedJSON, 
        default=dict, 
        server_default=text("'{}'::jsonb")
    )
    is_active: Mapped[bool] = mapped_column(default=True)

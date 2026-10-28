# app/modules/users/models.py
import uuid
from sqlalchemy import String, text, JSON, Boolean
from sqlalchemy.orm import mapped_column, Mapped
from app.db.base import Base
from app.db.mixins import TimestampMixin, AuditMixin, TenantMixin


class User(Base, TimestampMixin, AuditMixin, TenantMixin):
    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)

    full_name: Mapped[str] = mapped_column(String(255))
    email: Mapped[str] = mapped_column(String(255), unique=True)
    hashed_password: Mapped[str] = mapped_column(String(255))
    
    # 💡 Roles en formato JSON/JSONB
    roles: Mapped[list] = mapped_column(
        JSON, 
        default=lambda: ["RECEPTIONIST"], 
        server_default=text("'[\"RECEPTIONIST\"]'::jsonb")
    )
    # Roles posibles: "ADMIN", "DOCTOR", "RECEPTIONIST", "SUPER_ADMIN"
    
    # Estado activo de la cuenta
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, server_default=text('TRUE'))

    # 🔐 FASE 2: Autenticación Multifactor (MFA / TOTP RFC 6238)
    mfa_enabled: Mapped[bool] = mapped_column(Boolean, default=False, server_default=text('FALSE'))
    mfa_secret: Mapped[str | None] = mapped_column(String(255), nullable=True, default=None)

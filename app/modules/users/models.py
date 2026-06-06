# app/modules/users/models.py
import uuid
from sqlalchemy import String, text
from sqlalchemy.orm import mapped_column, Mapped
from sqlalchemy import JSON
from app.db.base import Base
from app.db.mixins import TimestampMixin, AuditMixin, TenantMixin


class User(Base, TimestampMixin, AuditMixin, TenantMixin):
    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)

    full_name: Mapped[str] = mapped_column(String(255))
    email: Mapped[str] = mapped_column(String(255), unique=True)
    hashed_password: Mapped[str] = mapped_column(String(255))
    
    roles: Mapped[list] = mapped_column(JSON, default=lambda: ["RECEPTIONIST"], server_default='["RECEPTIONIST"]::jsonb')
    # Roles posibles: "ADMIN", "DOCTOR", "RECEPTIONIST"
    
    # 🔐 LA COLUMNA AL ESTILO MODERNOCON VALOR POR DEFECTO AUTOMÁTICO
    is_active: Mapped[bool] = mapped_column(default=True, server_default=text('TRUE'))
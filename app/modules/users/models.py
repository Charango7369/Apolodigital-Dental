# app/modules/users/models.py
import uuid
from sqlalchemy import String
from sqlalchemy.orm import mapped_column, Mapped

from app.db.base import Base
from app.db.mixins import TimestampMixin, AuditMixin, TenantMixin


class User(Base, TimestampMixin, AuditMixin, TenantMixin):
    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)

    full_name: Mapped[str] = mapped_column(String(255))
    email: Mapped[str] = mapped_column(String(255), unique=True)
    hashed_password: Mapped[str] = mapped_column(String(255))
    role: Mapped[str] = mapped_column(String(50))
    
    
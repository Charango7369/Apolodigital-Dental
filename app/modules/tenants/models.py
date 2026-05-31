import uuid
from sqlalchemy import String
from sqlalchemy.orm import mapped_column, Mapped

from app.db.base import Base
from app.db.mixins import TimestampMixin, AuditMixin


class Tenant(Base, TimestampMixin, AuditMixin):
    __tablename__ = "tenants"

    # Nota: Tenant NO lleva TenantMixin porque es la raíz del tenant
    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)

    name: Mapped[str] = mapped_column(String(255))
    address: Mapped[str | None] = mapped_column(String(255), nullable=True)
    phone: Mapped[str | None] = mapped_column(String(50), nullable=True)
    is_active: Mapped[bool] = mapped_column(default=True)
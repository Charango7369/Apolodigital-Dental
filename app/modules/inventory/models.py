# app/modules/inventory/models.py
import uuid
from sqlalchemy import String, Integer, Numeric
from sqlalchemy.orm import mapped_column, Mapped

from app.db.base import Base
from app.db.mixins import TimestampMixin, AuditMixin, TenantMixin

class InventoryItem(Base, TimestampMixin, AuditMixin, TenantMixin):
    __tablename__ = "inventory"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    
    item_name: Mapped[str] = mapped_column(String(255))
    sku: Mapped[str] = mapped_column(String(100), nullable=True)  # Código de barras o SKU interno
    stock: Mapped[int] = mapped_column(Integer, default=0)
    stock_alert: Mapped[int] = mapped_column(Integer, default=5)  # Alerta si baja de este número
    price: Mapped[float] = mapped_column(Numeric(10, 2), default=0.00)
    is_active: Mapped[bool] = mapped_column(default=True)
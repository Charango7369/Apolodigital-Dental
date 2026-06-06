# app/modules/billing/models.py
import uuid
from sqlalchemy import String, Text, ForeignKey, Numeric, Boolean
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.db.mixins import TimestampMixin, AuditMixin, TenantMixin

class AccountReceivable(Base, TimestampMixin, AuditMixin, TenantMixin):
    __tablename__ = "accounts_receivable"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    patient_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("patients.id", ondelete="CASCADE"), nullable=False)
    
    # Manejo de dinero exacto con 2 decimales
    total_amount: Mapped[float] = mapped_column(Numeric(10, 2), nullable=False)
    balance_due: Mapped[float] = mapped_column(Numeric(10, 2), nullable=False)
    
    status: Mapped[str] = mapped_column(String(50), default="PENDING")
    description: Mapped[str] = mapped_column(Text, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

    # 🔗 Relación ORM: Una deuda tiene muchos pagos
    payments = relationship("Payment", back_populates="account", cascade="all, delete-orphan")


class Payment(Base, TimestampMixin, AuditMixin, TenantMixin):
    __tablename__ = "payments"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    account_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("accounts_receivable.id", ondelete="CASCADE"), nullable=False)
    
    amount_paid: Mapped[float] = mapped_column(Numeric(10, 2), nullable=False)
    payment_method: Mapped[str] = mapped_column(String(50), nullable=False)
    reference_number: Mapped[str] = mapped_column(String(100), nullable=True)
    notes: Mapped[str] = mapped_column(Text, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

    # 🔗 Relación ORM inversa
    account = relationship("AccountReceivable", back_populates="payments")
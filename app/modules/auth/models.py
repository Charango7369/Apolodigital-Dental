# app/modules/auth/models.py
import uuid
from datetime import datetime, timezone
from sqlalchemy import String, Boolean, DateTime, ForeignKey, text
from sqlalchemy.orm import mapped_column, Mapped, relationship
from app.db.base import Base


class RefreshToken(Base):
    """
    Modelo de persistencia para tokens de refresco con soporte de rotación (RTR)
    y detección forense de reuso (Token Family Reuse Detection).
    """
    __tablename__ = "refresh_tokens"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), 
        nullable=False, 
        index=True
    )
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("tenants.id", ondelete="CASCADE"), 
        nullable=False, 
        index=True
    )
    
    # Hash criptográfico SHA-256 del token plano (64 caracteres hexadecimales)
    token_hash: Mapped[str] = mapped_column(
        String(64), 
        unique=True, 
        nullable=False, 
        index=True
    )
    
    # Identificador de la familia de tokens para revocación en cascada ante reuso
    family_id: Mapped[uuid.UUID] = mapped_column(
        nullable=False, 
        index=True
    )
    
    # Estado de revocación
    is_revoked: Mapped[bool] = mapped_column(
        Boolean, 
        default=False, 
        server_default=text("FALSE"),
        nullable=False, 
        index=True
    )
    revoked_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), 
        nullable=True
    )
    
    # Puntero al nuevo token emitido en la rotación
    replaced_by: Mapped[uuid.UUID | None] = mapped_column(
        nullable=True
    )
    
    # Fechas de expiración y auditoría
    expires_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), 
        nullable=False, 
        index=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), 
        default=lambda: datetime.now(timezone.utc), 
        server_default=text("NOW()"),
        nullable=False
    )
    
    # Metadatos del cliente
    client_ip: Mapped[str | None] = mapped_column(String(45), nullable=True)
    user_agent: Mapped[str | None] = mapped_column(String(255), nullable=True)

    # Relaciones
    user = relationship("User", foreign_keys=[user_id])
    tenant = relationship("Tenant", foreign_keys=[tenant_id])

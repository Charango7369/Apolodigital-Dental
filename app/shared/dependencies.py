# app/shared/dependencies.py
from enum import Enum
from typing import Any, List, Optional
from uuid import UUID

from fastapi import Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from app.db.session import get_db
from app.core.tenant_context import apply_db_tenant_context
from app.modules.auth.dependencies import get_current_user, require_role
from app.modules.users.models import User as UserModel


class RoleEnum(str, Enum):
    SUPER_ADMIN = "SUPER_ADMIN"
    ADMIN = "ADMIN"
    DOCTOR = "DOCTOR"
    RECEPTIONIST = "RECEPTIONIST"


async def get_current_tenant_id(
    current_user: UserModel = Depends(get_current_user)
) -> UUID:
    """
    Extrae de forma estricta y segura el tenant_id del usuario autenticado en sesión.
    Default Deny: si el usuario no tiene tenant asignado, se deniega la petición.
    """
    if not current_user.tenant_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Operación no autorizada: usuario sin clínica asignada."
        )
    return current_user.tenant_id


async def get_tenant_db(
    db: AsyncSession = Depends(get_db),
    current_user: UserModel = Depends(get_current_user)
) -> AsyncSession:
    """
    Dependencia que garantiza que la sesión de base de datos esté
    configurada con el contexto RLS del tenant del usuario actual.
    """
    is_superadmin = "SUPER_ADMIN" in (current_user.roles if isinstance(current_user.roles, list) else [])
    await apply_db_tenant_context(db, tenant_id=current_user.tenant_id, bypass=is_superadmin)
    return db


async def verify_tenant_entity(
    db: AsyncSession,
    model: Any,
    entity_id: UUID,
    tenant_id: UUID,
    entity_name: str = "Recurso",
    active_only: bool = True
) -> Any:
    """
    Validador BOLA / IDOR reutilizable.
    Garantiza que la entidad consultada exista Y pertenezca al tenant del solicitante.
    Retorna 404 en lugar de 403 para prevenir enumeración inter-tenant de identificadores.
    """
    conditions = [
        model.id == entity_id,
        model.tenant_id == tenant_id
    ]
    if active_only and hasattr(model, "is_active"):
        conditions.append(model.is_active == True)

    query = select(model).where(*conditions)
    result = await db.execute(query)
    entity = result.scalar_one_or_none()

    if not entity:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"{entity_name} no encontrado en esta clínica."
        )
    return entity

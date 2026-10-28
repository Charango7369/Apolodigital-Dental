# app/modules/tenants/staff_router.py
import secrets
import string
import traceback
from datetime import datetime, timezone
from uuid import UUID
from typing import List

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from app.db.session import get_db
import app.models
from app.core.rate_limiter import rate_limiter_reset
from app.modules.auth.service import AuthService
from app.modules.tenants.staff_schemas import (
    ClinicStaffCreate,
    ClinicStaffUpdate,
    ClinicStaffResponse,
    PasswordResetRequest,
    PasswordResetResponse,
)
from app.modules.tenants.models import Tenant as TenantModel
from app.modules.users.models import User as UserModel
from app.core.security import hash_password
from app.modules.auth.dependencies import get_current_user


def generate_temporary_password(length: int = 8) -> str:
    """Genera una contraseña temporal segura y fácil de dictar o copiar."""
    alphabet = string.ascii_letters + string.digits
    suffix = "".join(secrets.choice(alphabet) for _ in range(length))
    return f"Apolo-{suffix}"


async def require_platform_or_clinic_admin(
    clinic_id: UUID,
    current_user: UserModel = Depends(get_current_user),
) -> UserModel:
    """
    Verifica que el usuario sea SUPER_ADMIN de la plataforma
    o ADMIN específico de la clínica solicitada.
    """
    user_roles = current_user.roles if isinstance(current_user.roles, list) else []
    is_super = "SUPER_ADMIN" in user_roles
    is_clinic_admin = "ADMIN" in user_roles and current_user.tenant_id == clinic_id

    if not (is_super or is_clinic_admin):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Acceso denegado. Se requiere rol SUPER_ADMIN de la plataforma o ADMIN de esta clínica.",
        )
    return current_user


router = APIRouter(prefix="/clinics", tags=["Clinics Staff"])
tenants_staff_router = APIRouter(prefix="/tenants", tags=["Tenants Staff"])


def register_staff_routes(r: APIRouter):
    # 🔍 1. LISTAR PERSONAL DE UNA CLÍNICA
    @r.get("/{clinic_id}/staff", response_model=List[ClinicStaffResponse])
    async def get_clinic_staff(
        clinic_id: UUID,
        db: AsyncSession = Depends(get_db),
        current_user: UserModel = Depends(require_platform_or_clinic_admin),
    ):
        # Validar existencia de la clínica
        tenant = (await db.execute(select(TenantModel).where(TenantModel.id == clinic_id))).scalar_one_or_none()
        if not tenant:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Clínica no encontrada.")

        query = select(UserModel).where(UserModel.tenant_id == clinic_id).order_by(UserModel.created_at.desc())
        result = await db.execute(query)
        return result.scalars().all()

    # ➕ 2. CREAR NUEVO USUARIO DENTRO DE LA CLÍNICA
    @r.post("/{clinic_id}/staff", response_model=ClinicStaffResponse, status_code=status.HTTP_201_CREATED)
    async def create_clinic_staff(
        clinic_id: UUID,
        payload: ClinicStaffCreate,
        db: AsyncSession = Depends(get_db),
        current_user: UserModel = Depends(require_platform_or_clinic_admin),
    ):
        try:
            # Validar clínica
            tenant = (await db.execute(select(TenantModel).where(TenantModel.id == clinic_id))).scalar_one_or_none()
            if not tenant:
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Clínica no encontrada.")

            # Validar email único globalmente
            existing = (await db.execute(select(UserModel).where(UserModel.email == payload.email))).scalar_one_or_none()
            if existing:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail="Ya existe un usuario registrado con ese correo electrónico en el sistema.",
                )

            new_user = UserModel(
                full_name=payload.full_name.strip(),
                email=payload.email.lower().strip(),
                hashed_password=hash_password(payload.password),
                roles=payload.validate_roles(),
                is_active=payload.is_active,
                tenant_id=clinic_id,
            )
            db.add(new_user)
            await db.commit()
            await db.refresh(new_user)
            return new_user
        except HTTPException:
            raise
        except Exception as e:
            traceback.print_exc()
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Error interno al crear personal: {str(e)}",
            )

    # ✏️ 3. EDITAR INFORMACIÓN DE PERSONAL
    @r.put("/{clinic_id}/staff/{user_id}", response_model=ClinicStaffResponse)
    async def update_clinic_staff(
        clinic_id: UUID,
        user_id: UUID,
        payload: ClinicStaffUpdate,
        db: AsyncSession = Depends(get_db),
        current_user: UserModel = Depends(require_platform_or_clinic_admin),
    ):
        query = select(UserModel).where(UserModel.id == user_id, UserModel.tenant_id == clinic_id)
        result = await db.execute(query)
        target_user = result.scalar_one_or_none()

        if not target_user:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Usuario no encontrado en esta clínica.")

        # Si se actualiza email, verificar unicidad
        if payload.email and payload.email.lower().strip() != target_user.email:
            existing = (await db.execute(select(UserModel).where(UserModel.email == payload.email.lower().strip()))).scalar_one_or_none()
            if existing:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail="El correo electrónico ya se encuentra en uso por otra cuenta.",
                )
            target_user.email = payload.email.lower().strip()

        if payload.full_name is not None:
            target_user.full_name = payload.full_name.strip()

        if payload.roles is not None:
            target_user.roles = payload.validate_roles()

        if payload.is_active is not None:
            target_user.is_active = payload.is_active

        if hasattr(target_user, "updated_at"):
            target_user.updated_at = datetime.now(timezone.utc)

        await db.commit()
        await db.refresh(target_user)
        return target_user

    # 🔑 4. RESETEAR CONTRASEÑA CON RATE LIMITING (5 INTENTOS / HORA) Y REVOCACIÓN DE SESIÓN
    @r.post(
        "/{clinic_id}/staff/{user_id}/reset-password", 
        response_model=PasswordResetResponse,
        dependencies=[Depends(rate_limiter_reset)]
    )
    async def reset_clinic_staff_password(
        clinic_id: UUID,
        user_id: UUID,
        payload: PasswordResetRequest,
        db: AsyncSession = Depends(get_db),
        current_user: UserModel = Depends(require_platform_or_clinic_admin),
    ):
        query = select(UserModel).where(UserModel.id == user_id, UserModel.tenant_id == clinic_id)
        result = await db.execute(query)
        target_user = result.scalar_one_or_none()

        if not target_user:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Usuario no encontrado en esta clínica.")

        temporary_pwd = None
        if payload.new_password and payload.new_password.strip():
            plain_pwd = payload.new_password.strip()
            msg = "Contraseña actualizada exitosamente."
        else:
            temporary_pwd = generate_temporary_password(8)
            plain_pwd = temporary_pwd
            msg = "Contraseña temporal generada con éxito."

        target_user.hashed_password = hash_password(plain_pwd)
        if hasattr(target_user, "updated_at"):
            target_user.updated_at = datetime.now(timezone.utc)

        # 🛑 Medida defensiva: Revocar todas las sesiones activas del usuario cuya contraseña fue reseteada
        await AuthService.revoke_all_user_sessions(db, target_user.id)

        await db.commit()
        await db.refresh(target_user)

        return PasswordResetResponse(
            message=msg,
            user_id=target_user.id,
            temporary_password=temporary_pwd,
        )


# Registrar rutas en ambos routers para máxima compatibilidad
register_staff_routes(router)
register_staff_routes(tenants_staff_router)

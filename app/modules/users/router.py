# app/modules/users/router.py
import traceback
from datetime import datetime, timezone
from uuid import UUID
from typing import List

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from app.db.session import get_db
from app.modules.users.schemas import UserCreate, UserUpdate, UserResponse
from app.modules.users.models import User as UserModel
from app.core.security import hash_password
from app.modules.auth.dependencies import get_current_user, require_role

router = APIRouter(prefix="/users", tags=["Users"])

# Solo el/los ADMIN de una clínica pueden gestionar el personal de ESA clínica.
require_admin = require_role(["ADMIN"])


# 🎫 PERFIL DEL USUARIO AUTENTICADO (sin cambios de comportamiento)
@router.get("/me", response_model=UserResponse)
async def get_my_profile(current_user: UserModel = Depends(get_current_user)):
    return current_user


# 🔍 1. LISTAR EL PERSONAL DE MI PROPIA CLÍNICA
@router.get("", response_model=List[UserResponse])
async def get_my_clinic_users(
    db: AsyncSession = Depends(get_db),
    current_user: UserModel = Depends(get_current_user),
):
    query = select(UserModel).where(
        UserModel.tenant_id == current_user.tenant_id
    ).order_by(UserModel.created_at.desc() if hasattr(UserModel, "created_at") else UserModel.id)
    result = await db.execute(query)
    return result.scalars().all()


# ➕ 2. CREAR UN NUEVO MIEMBRO DEL EQUIPO (siempre dentro de MI clínica)
@router.post("", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
async def create_user(
    payload: UserCreate,
    db: AsyncSession = Depends(get_db),
    current_user: UserModel = Depends(require_admin),
):
    try:
        # Email único a nivel de toda la plataforma (la columna es UNIQUE)
        existing = await db.execute(select(UserModel).where(UserModel.email == payload.email))
        if existing.scalar_one_or_none():
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Ya existe un usuario registrado con ese correo electrónico."
            )

        new_user = UserModel(
            full_name=payload.full_name,
            email=payload.email,
            hashed_password=hash_password(payload.password),
            roles=payload.validate_roles(),
            tenant_id=current_user.tenant_id,  # 🚨 SIEMPRE la clínica del ADMIN que crea, nunca del cliente
            is_active=True,
        )

        db.add(new_user)
        await db.commit()
        await db.refresh(new_user)
        return new_user

    except HTTPException:
        await db.rollback()
        raise
    except Exception as e:
        await db.rollback()
        print("\n❌ ====== ¡FALLO AL CREAR USUARIO! ====== ❌")
        traceback.print_exc()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Error al crear el usuario: {str(e)}"
        )


# 🔄 3. EDITAR ROL / NOMBRE / ESTADO DE UN MIEMBRO DE MI CLÍNICA
@router.patch("/{user_id}", response_model=UserResponse)
async def update_user(
    user_id: UUID,
    payload: UserUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: UserModel = Depends(require_admin),
):
    query = select(UserModel).where(
        UserModel.id == user_id,
        UserModel.tenant_id == current_user.tenant_id,  # nunca tocar usuarios de otra clínica
    )
    result = await db.execute(query)
    target_user = result.scalar_one_or_none()

    if not target_user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Usuario no encontrado en esta clínica.")

    update_data = payload.model_dump(exclude_unset=True)

    # 🛡️ Salvaguarda: evitar que la clínica se quede sin ningún ADMIN activo
    would_remove_admin = (
        target_user.id == current_user.id
        and (
            ("roles" in update_data and "ADMIN" not in update_data["roles"])
            or ("is_active" in update_data and update_data["is_active"] is False)
        )
    )
    if would_remove_admin:
        other_admins = await db.execute(
            select(UserModel).where(
                UserModel.tenant_id == current_user.tenant_id,
                UserModel.id != current_user.id,
                UserModel.is_active == True,
            )
        )
        remaining = [u for u in other_admins.scalars().all() if "ADMIN" in (u.roles or [])]
        if not remaining:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="No puedes quitarte el rol de ADMIN o desactivarte: eres el único administrador activo de esta clínica."
            )

    if "roles" in update_data:
        cleaned = [r for r in update_data["roles"] if r in ("ADMIN", "DOCTOR", "RECEPTIONIST")]
        update_data["roles"] = cleaned or ["RECEPTIONIST"]

    for key, value in update_data.items():
        setattr(target_user, key, value)

    if hasattr(target_user, "updated_at"):
        target_user.updated_at = datetime.now(timezone.utc)

    await db.commit()
    await db.refresh(target_user)
    return target_user
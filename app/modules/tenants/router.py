# app/modules/tenants/router.py
import traceback
from datetime import datetime, timezone
from uuid import UUID
from typing import List

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from app.db.session import get_db
from app.modules.tenants.schemas import (
    TenantCreate, TenantUpdate, TenantResponse, TenantWithAdminResponse
)
from app.modules.tenants.models import Tenant as TenantModel
from app.modules.users.models import User as UserModel
from app.core.security import hash_password
from app.modules.auth.dependencies import get_current_user, require_role

router = APIRouter(prefix="/tenants", tags=["Tenants"])

# 🚨 Todo este módulo es exclusivo del dueño de la plataforma.
# Antes NO tenía ninguna protección — cualquiera podía listar o crear
# clínicas sin siquiera iniciar sesión. Ahora requiere el rol SUPER_ADMIN.
require_super_admin = require_role(["SUPER_ADMIN"])


# ➕ 1. CREAR CLÍNICA NUEVA + SU PRIMER ADMIN (operación atómica)
@router.post("", response_model=TenantWithAdminResponse, status_code=status.HTTP_201_CREATED)
async def create_tenant(
    payload: TenantCreate,
    db: AsyncSession = Depends(get_db),
    current_user: UserModel = Depends(require_super_admin),
):
    try:
        ahora = datetime.now(timezone.utc)

        # 1. Verificamos que el correo del admin no esté ya en uso en NINGUNA clínica
        existing = await db.execute(select(UserModel).where(UserModel.email == payload.admin_email))
        if existing.scalar_one_or_none():
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Ya existe un usuario registrado con ese correo electrónico."
            )

        # 2. Creamos la clínica
        new_tenant = TenantModel(
            name=payload.name,
            address=payload.address,
            phone=payload.phone,
            is_active=True,
        )
        db.add(new_tenant)
        await db.flush()  # obtenemos new_tenant.id sin perder la transacción

        # 3. Creamos su primer ADMIN, ya vinculado a esa clínica
        new_admin = UserModel(
            full_name=payload.admin_full_name,
            email=payload.admin_email,
            hashed_password=hash_password(payload.admin_password),
            roles=["ADMIN"],
            tenant_id=new_tenant.id,
            is_active=True,
        )
        db.add(new_admin)

        await db.commit()
        await db.refresh(new_tenant)
        await db.refresh(new_admin)

        return TenantWithAdminResponse(
            tenant=TenantResponse.model_validate(new_tenant),
            admin_email=new_admin.email,
            admin_id=new_admin.id,
        )

    except HTTPException:
        await db.rollback()
        raise
    except Exception as e:
        await db.rollback()
        print("\n❌ ====== ¡FALLO AL CREAR CLÍNICA! ====== ❌")
        traceback.print_exc()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Error al crear la clínica: {str(e)}"
        )


# 🔍 2. LISTAR TODAS LAS CLÍNICAS DE LA PLATAFORMA
@router.get("", response_model=List[TenantResponse])
async def get_tenants(
    db: AsyncSession = Depends(get_db),
    current_user: UserModel = Depends(require_super_admin),
):
    result = await db.execute(select(TenantModel).order_by(TenantModel.created_at.desc()))
    return result.scalars().all()


# 🎯 3. OBTENER UNA CLÍNICA ESPECÍFICA
@router.get("/{tenant_id}", response_model=TenantResponse)
async def get_tenant(
    tenant_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: UserModel = Depends(require_super_admin),
):
    result = await db.execute(select(TenantModel).where(TenantModel.id == tenant_id))
    tenant = result.scalar_one_or_none()
    if not tenant:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Clínica no encontrada.")
    return tenant


# 🔄 4. EDITAR / ACTIVAR / DESACTIVAR UNA CLÍNICA
@router.patch("/{tenant_id}", response_model=TenantResponse)
async def update_tenant(
    tenant_id: UUID,
    payload: TenantUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: UserModel = Depends(require_super_admin),
):
    result = await db.execute(select(TenantModel).where(TenantModel.id == tenant_id))
    tenant = result.scalar_one_or_none()
    if not tenant:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Clínica no encontrada.")

    update_data = payload.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(tenant, key, value)

    await db.commit()
    await db.refresh(tenant)
    return tenant
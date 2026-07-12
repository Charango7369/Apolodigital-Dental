# app/modules/auth/router.py
import json
import traceback
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from app.db.session import get_db
from app.core.security import verify_password, create_access_token
from app.modules.users.models import User as UserModel
from app.modules.auth.schemas import LoginResponse, UserResponse

router = APIRouter(prefix="/auth", tags=["Authentication"])


def _build_user_response(user: UserModel) -> UserResponse:
    """
    Convierte el modelo SQLAlchemy en el schema Pydantic.
    - Convierte UUID a string (Pydantic lo serializa automáticamente, pero lo forzamos para claridad).
    - Serializa `roles` (list) a JSON string, como lo espera el frontend.
    """
    roles_raw = user.roles if isinstance(user.roles, list) else ["RECEPTIONIST"]
    roles_json = json.dumps(roles_raw)

    return UserResponse(
        id=user.id,
        full_name=user.full_name,
        email=user.email,
        roles=roles_json,
        tenant_id=user.tenant_id,
    )


@router.post("/login", response_model=LoginResponse)
async def login_for_access_token(
    form_data: OAuth2PasswordRequestForm = Depends(),
    db: AsyncSession = Depends(get_db),
):
    try:
        print(f"\n[DEBUG LOGIN] Intentando login para: '{form_data.username}'")

        # 🔍 1. Buscar al usuario
        query = select(UserModel).where(UserModel.email == form_data.username)
        result = await db.execute(query)
        user = result.scalar_one_or_none()

        print(f"[DEBUG LOGIN] Resultado de la BD: {user}")

        # 🛑 2. Si no existe o está inactivo, rebotamos
        if not user:
            print("[DEBUG LOGIN] FALLO: El usuario no existe en la base de datos.")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Correo electrónico o contraseña incorrectos",
                headers={"WWW-Authenticate": "Bearer"},
            )

        if not user.is_active:
            print("[DEBUG LOGIN] FALLO: El usuario existe pero is_active es False.")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Correo electrónico o contraseña incorrectos",
                headers={"WWW-Authenticate": "Bearer"},
            )

        # 🔑 3. Verificar la contraseña
        print("[DEBUG LOGIN] Usuario encontrado. Verificando hash de contraseña...")
        is_password_valid = verify_password(form_data.password, user.hashed_password)
        print(f"[DEBUG LOGIN] ¿Contraseña válida?: {is_password_valid}")

        if not is_password_valid:
            print("[DEBUG LOGIN] FALLO: La contraseña no coincide con el hash.")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Correo electrónico o contraseña incorrectos",
                headers={"WWW-Authenticate": "Bearer"},
            )

        # 🎫 4. Credenciales válidas — Generar token JWT
        print("[DEBUG LOGIN] ¡Éxito! Generando token JWT...")
        user_id_str = str(user.id)
        access_token = create_access_token(subject=user_id_str)

        # 👤 5. Construir la respuesta con los datos del usuario
        user_response = _build_user_response(user)

        print(f"[DEBUG LOGIN] Respondiendo con token + user (id={user_response.id}, tenant={user_response.tenant_id})")

        return LoginResponse(
            access_token=access_token,
            token_type="bearer",
            user=user_response,
        )

    except Exception as e:
        print("\n❌ ====== ¡CAPTURA DE ERROR EN POST /AUTH/LOGIN ====== ❌")
        traceback.print_exc()
        print("❌ ======================================================= \n")
        if isinstance(e, HTTPException):
            raise e
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error interno en el login: {str(e)}",
        )
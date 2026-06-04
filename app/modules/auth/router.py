# app/modules/auth/router.py
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
import traceback  # 👈 Para capturar el culpable real en la consola de Railway

from app.db.session import get_db
from app.core.security import verify_password, create_access_token
from app.modules.users.models import User as UserModel
from app.modules.auth.schemas import Token

router = APIRouter(prefix="/auth", tags=["Authentication"])

@router.post("/login", response_model=Token)
async def login_for_access_token(
    form_data: OAuth2PasswordRequestForm = Depends(), 
    db: AsyncSession = Depends(get_db)
):
    try:
        # 🔍 1. Buscar al usuario por email (Swagger manda el email en form_data.username)
        query = select(UserModel).where(UserModel.email == form_data.username)
        result = await db.execute(query)
        user = result.scalar_one_or_none()

        # 🛑 2. Si no existe o está inactivo, rebotamos
        if not user or not user.is_active:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Correo electrónico o contraseña incorrectos",
                headers={"WWW-Authenticate": "Bearer"},
            )

        # 🔑 3. Verificar la contraseña usando el motor nativo de bcrypt
        if not verify_password(form_data.password, user.hashed_password):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Correo electrónico o contraseña incorrectos",
                headers={"WWW-Authenticate": "Bearer"},
            )

        # 🎫 4. Credenciales válidas: Forzamos el ID de UUID a String para evitar que python-jose colapse
        user_id_str = str(user.id)
        access_token = create_access_token(subject=user_id_str)
        
        return {"access_token": access_token, "token_type": "bearer"}

    except Exception as e:
        # 🚨 Si algo falla, lo imprimimos completo en la consola de Railway
        print("\n❌ ====== ¡CAPTURA DE ERROR EN POST /AUTH/LOGIN ====== ❌")
        traceback.print_exc()
        print("❌ ======================================================= \n")
        # Si ya es una excepción de FastAPI, la dejamos pasar limpia
        if isinstance(e, HTTPException):
            raise e
        # Si es un error interno, devolvemos los detalles para no andar a ciegas
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error interno en el login: {str(e)}"
        )
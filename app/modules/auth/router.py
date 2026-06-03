# app/modules/auth/router.py
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

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
    # 🔍 1. Buscar al usuario por su email (Swagger manda el email en el campo 'username')
    query = select(UserModel).where(UserModel.email == form_data.username)
    result = await db.execute(query)
    user = result.scalar_one_or_none()

    # 🛑 2. Si no existe o está inactivo, rechazamos la entrada
    if not user or not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Correo electrónico o contraseña incorrectos",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # 🔑 3. Verificar si la contraseña ingresada coincide con el hash almacenado
    if not verify_password(form_data.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Correo electrónico o contraseña incorrectos",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # 🎫 4. Credenciales válidas: Generamos el Token JWT usando el ID del usuario
    access_token = create_access_token(subject=user.id)
    
    return {"access_token": access_token, "token_type": "bearer"}
# app/modules/auth/router.py
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

# Importamos la dependencia que acabas de encontrar
from app.db.session import get_db

# Seguridad y Esquemas
from app.core.security import verify_password, create_access_token, create_refresh_token
from app.models import User  # Ajusta si tu modelo User está en otra ruta

# IMPORTANTE: Asegúrate de que esta ruta coincida con tu esquema de LoginRequest
from app.schemas.auth import LoginRequest  

router = APIRouter(prefix="/auth", tags=["Auth"])

@router.post("/login")
async def login(payload: LoginRequest, db: AsyncSession = Depends(get_db)):
    """
    Endpoint del Portal Global Único para autenticar usuarios
    y emitir tokens con aislamiento Multi-Tenant.
    """
    # 1. Búsqueda global por email
    result = await db.execute(select(User).where(User.email == payload.email))
    user = result.scalar_one_or_none()
    
    # 2. Validación de credenciales
    if not user or not verify_password(payload.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="El correo electrónico o la contraseña son incorrectos."
        )
    
    # 3. Inyección del tenant_id en el payload del JWT
    token_payload = {
        "sub": str(user.id),
        "tenant_id": str(user.tenant_id),  # Clave para el aislamiento de datos
        "role": getattr(user, "role", "user")
    }
    
    # 4. Generación de tokens con la nueva lógica segura
    access_token = create_access_token(data=token_payload)
    refresh_token = create_refresh_token(data=token_payload)
    
    return {
        "access_token": access_token,
        "refresh_token": refresh_token,
        "token_type": "bearer"
    }
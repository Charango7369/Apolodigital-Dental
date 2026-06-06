# app/modules/auth/dependencies.py
from typing import List
from uuid import UUID

from fastapi import HTTPException, status, Depends
from fastapi.security import OAuth2PasswordBearer
from jose import jwt, JWTError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from app.db.session import get_db
from app.core.security import SECRET_KEY, ALGORITHM
from app.modules.users.models import User as UserModel
from app.modules.auth.schemas import TokenData

# Le dice a FastAPI dónde está el endpoint para pedir el token de inicio de sesión
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="auth/login")

async def get_current_user(
    token: str = Depends(oauth2_scheme), 
    db: AsyncSession = Depends(get_db)
) -> UserModel:
    """
    Dependencia global para proteger rutas. Lee el token JWT, lo valida,
    y extrae el usuario completo (incluyendo su tenant_id en secreto).
    """
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="No se pudieron validar las credenciales de acceso",
        headers={"WWW-Authenticate": "Bearer"},
    )
    
    try:
        # 🪙 1. Desencriptamos el Token JWT recibido en las cabeceras
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        user_id: str = payload.get("sub")
        
        if user_id is None:
            raise credentials_exception
            
        token_data = TokenData(user_id=user_id)
    except JWTError:
        raise credentials_exception

    # 🔍 2. Buscamos de forma asíncrona al dueño del token en Postgres
    query = select(UserModel).where(UserModel.id == UUID(token_data.user_id))
    result = await db.execute(query)
    user = result.scalar_one_or_none()

    # 🛑 3. Validamos que exista y que no esté baneado/inactivo
    if user is None:
        raise credentials_exception
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, 
            detail="El usuario se encuentra inactivo"
        )
        
    # 🎯 ¡ÉXITO! Devolvemos el objeto usuario con su respectivo tenant_id
    return user

def require_role(allowed_roles: List[str]):
    """
    Fábrica de dependencias RBAC.
    Verifica si el usuario tiene al menos UNO de los roles permitidos en su arreglo de roles (JSONB).
    """
    async def role_checker(current_user: UserModel = Depends(get_current_user)) -> UserModel:
        
        # current_user.roles es una lista, ej: ["ADMIN", "DOCTOR"]
        # allowed_roles es una lista pasada en el router, ej: ["ADMIN"]
        has_permission = any(role in allowed_roles for role in current_user.roles)
        
        if not has_permission:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Acceso denegado. Se requiere al menos uno de estos roles: {', '.join(allowed_roles)}"
            )
        return current_user
    
    return role_checker
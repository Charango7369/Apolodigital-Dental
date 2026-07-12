# app/modules/auth/dependencies.py
from typing import List
from uuid import UUID
import traceback
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
    Dependencia global blindada. 
    Atrapa errores de formato, UUID y base de datos sin generar un 500.
    """
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="No se pudieron validar las credenciales de acceso",
        headers={"WWW-Authenticate": "Bearer"},
    )
    
    try:
        # 1. Decodificación base
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        user_id_str: str = payload.get("sub")
        
        if user_id_str is None:
            raise credentials_exception
            
        # 🛡️ 2. SANITIZACIÓN CRÍTICA: Intentamos convertir el string a UUID de forma segura
        try:
            valid_uuid = UUID(user_id_str)
        except ValueError:
            print(f"\n❌ [ADVERTENCIA DE SEGURIDAD] El token contiene '{user_id_str}', que NO es un UUID válido. Rechazando acceso.\n")
            raise credentials_exception

    except JWTError:
        raise credentials_exception

    # 🔍 3. Búsqueda en la base de datos protegida
    try:
        query = select(UserModel).where(UserModel.id == valid_uuid)
        result = await db.execute(query)
        user = result.scalar_one_or_none()
    except Exception as e:
        print("\n❌ ====== ERROR DE BASE DE DATOS EN AUTENTICACIÓN ====== ❌")
        traceback.print_exc()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, 
            detail="Fallo interno al consultar la identidad"
        )

    # 🛑 4. Validación final de existencia y estado
    if user is None:
        raise credentials_exception
        
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, 
            detail="El usuario se encuentra inactivo"
        )
        
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
# app/modules/auth/dependencies.py
from typing import List
from uuid import UUID
import logging
from fastapi import HTTPException, status, Depends
from fastapi.security import OAuth2PasswordBearer
from jose import jwt, JWTError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from app.db.session import get_db
from app.core.security import SECRET_KEY, ALGORITHM
from app.core.cache import token_cache
from app.modules.users.models import User as UserModel
from app.modules.auth.schemas import TokenData

logger = logging.getLogger(__name__)

# Configuración del esquema de autenticación OpenAPI
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="auth/login")


async def get_current_user(
    token: str = Depends(oauth2_scheme), 
    db: AsyncSession = Depends(get_db)
) -> UserModel:
    """
    Dependencia global blindada:
    1. Decodifica el JWT y valida la firma estricta.
    2. Valida tipo de token (rechaza tokens con scope 'mfa_pending' o tipos no autorizados).
    3. Comprueba revocación distribuida mediante JTI en caché/Redis.
    4. Sanitiza y valida el identificador UUID del sujeto.
    5. Consulta la base de datos y verifica que la cuenta esté activa.
    """
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="No se pudieron validar las credenciales de acceso",
        headers={"WWW-Authenticate": "Bearer"},
    )
    
    try:
        # 1. Decodificación y validación de firma
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        
        # 🛑 2. Validación de Tipo y Scope de Token
        # Un token temporal de desafío MFA NO debe poder acceder a los endpoints protegidos
        scope = payload.get("scope")
        token_type = payload.get("type", "access")
        if scope == "mfa_pending" or token_type == "mfa_challenge":
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Token de autorización parcial. Se requiere completar el segundo factor de autenticación (MFA).",
                headers={"WWW-Authenticate": "Bearer"},
            )
        if token_type not in ("access", None):
            raise credentials_exception

        # 🛑 3. Verificación de Revocación Distribuida (JTI)
        jti = payload.get("jti")
        if jti and await token_cache.is_token_revoked(jti):
            logger.warning(f"[AUTH] Intento de acceso con token revocado: jti={jti}")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="El token de acceso ha sido revocado. Inicie sesión nuevamente.",
                headers={"WWW-Authenticate": "Bearer"},
            )

        user_id_str: str = payload.get("sub")
        if user_id_str is None:
            raise credentials_exception
            
        # 🛡️ 4. Sanitización estricta de UUID
        try:
            valid_uuid = UUID(user_id_str)
        except ValueError:
            logger.warning(f"[ADVERTENCIA DE SEGURIDAD] Token contiene sub inválido: '{user_id_str}'")
            raise credentials_exception

    except JWTError:
        raise credentials_exception

    # 🔍 5. Búsqueda en la base de datos protegida
    try:
        query = select(UserModel).where(UserModel.id == valid_uuid)
        result = await db.execute(query)
        user = result.scalar_one_or_none()
    except Exception as e:
        logger.error(f"Fallo de BD en autenticación: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, 
            detail="Fallo interno al consultar la identidad"
        )

    # 🛑 6. Validación de existencia y estado de actividad
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
    Fábrica de dependencias RBAC con Default Deny.
    Verifica si el usuario tiene al menos UNO de los roles permitidos en su arreglo de roles (JSONB),
    o si posee el rol SUPER_ADMIN de la plataforma.
    """
    async def role_checker(current_user: UserModel = Depends(get_current_user)) -> UserModel:
        user_roles = current_user.roles if isinstance(current_user.roles, list) else []
        
        # SUPER_ADMIN posee acceso global
        if "SUPER_ADMIN" in user_roles:
            return current_user

        has_permission = any(role in allowed_roles for role in user_roles)
        if not has_permission:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Acceso denegado. Se requiere al menos uno de estos roles: {', '.join(allowed_roles)}"
            )
        return current_user
    
    return role_checker

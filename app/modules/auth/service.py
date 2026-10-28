# app/modules/auth/service.py
"""
Servicio de Autenticación, Gestión de Sesiones y Rotación de Tokens (RTR).
Implementa:
- Refresh Token Rotation (RTR) con Token Families.
- Detección forense de reuso de tokens de refresco (Token Family Invalidation).
- Emisión de tokens de acceso efímeros (15 minutos).
- Revocación distribuida en base de datos y caché.
"""
import logging
import uuid
from datetime import datetime, timedelta, timezone
from typing import Optional, Tuple

from fastapi import HTTPException, status
from sqlalchemy import update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from app.core.cache import token_cache
from app.core.config import settings
from app.core.security import (
    create_access_token,
    generate_refresh_token_pair,
    hash_token,
)
from app.modules.auth.models import RefreshToken
from app.modules.users.models import User as UserModel

logger = logging.getLogger(__name__)


class AuthService:
    @staticmethod
    async def create_user_session(
        db: AsyncSession,
        user: UserModel,
        client_ip: Optional[str] = None,
        user_agent: Optional[str] = None,
    ) -> Tuple[str, str]:
        """
        Inicia una nueva sesión autenticada:
        1. Crea un identificador de familia de tokens único (family_id).
        2. Genera un Access Token firmado de corta duración (15 min).
        3. Genera y persiste un Refresh Token hasheado (7 días).
        Retorna: (access_token, raw_refresh_token)
        """
        family_id = uuid.uuid4()
        now = datetime.now(timezone.utc)
        expires_at = now + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS)

        # 1. Access Token JWT
        roles_list = user.roles if isinstance(user.roles, list) else ["RECEPTIONIST"]
        access_token = create_access_token(
            subject=str(user.id),
            tenant_id=user.tenant_id,
            roles=roles_list,
        )

        # 2. Refresh Token criptográfico y su hash
        raw_refresh_token, token_hash = generate_refresh_token_pair()

        # 3. Persistencia en BD
        db_token = RefreshToken(
            id=uuid.uuid4(),
            user_id=user.id,
            tenant_id=user.tenant_id,
            token_hash=token_hash,
            family_id=family_id,
            is_revoked=False,
            expires_at=expires_at,
            created_at=now,
            client_ip=client_ip,
            user_agent=user_agent,
        )
        db.add(db_token)
        await db.commit()

        logger.info(f"Sesión iniciada exitosamente para usuario {user.id}. Familia: {family_id}")
        return access_token, raw_refresh_token

    @staticmethod
    async def rotate_refresh_token(
        db: AsyncSession,
        raw_refresh_token: str,
        client_ip: Optional[str] = None,
        user_agent: Optional[str] = None,
    ) -> Tuple[str, str, UserModel]:
        """
        Ejecuta la Rotación Automática de Token de Refresco (RTR):
        - Valida el token contra la base de datos por su hash SHA-256.
        - Si el token ya fue revocado: DETECCIÓN DE REUSO -> Invalida inmediatamente toda la familia.
        - Si expiró: Rechaza la petición.
        - Si es válido: Revoca el token actual, emite un nuevo par de Access Token + Refresh Token
          dentro de la misma familia y actualiza el puntero 'replaced_by'.
        Retorna: (new_access_token, new_raw_refresh_token, user)
        """
        token_hash = hash_token(raw_refresh_token)

        # 1. Buscar el token en la base de datos
        query = select(RefreshToken).where(RefreshToken.token_hash == token_hash)
        result = await db.execute(query)
        db_token = result.scalar_one_or_none()

        if not db_token:
            logger.warning("[AUTH] Intento de rotación con token de refresco inexistente.")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Token de refresco inválido o desconocido.",
                headers={"WWW-Authenticate": "Bearer"},
            )

        now = datetime.now(timezone.utc)

        # 🚨 2. DETECCIÓN CRÍTICA DE REUSO (Token Reuse / Replay Attack Detection)
        if db_token.is_revoked:
            logger.error(
                f"[SECURITY ALERT] ¡Intento de reutilización de Refresh Token detectado! "
                f"Usuario: {db_token.user_id}, Familia: {db_token.family_id}, IP: {client_ip}."
            )
            # Acción ofensiva defensiva inmediata: Revocar TODA la familia de tokens
            await db.execute(
                update(RefreshToken)
                .where(RefreshToken.family_id == db_token.family_id)
                .values(is_revoked=True, revoked_at=now)
            )
            await db.commit()

            # Revocar también en caché distribuida
            await token_cache.revoke_family(str(db_token.family_id))

            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Posible intento de robo de sesión detectado. Todas las sesiones activas han sido invalidadas.",
                headers={"WWW-Authenticate": "Bearer"},
            )

        # 3. Comprobar expiración
        if db_token.expires_at < now:
            db_token.is_revoked = True
            db_token.revoked_at = now
            await db.commit()
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="El token de refresco ha expirado. Inicie sesión nuevamente.",
                headers={"WWW-Authenticate": "Bearer"},
            )

        # 4. Obtener y validar usuario
        user_query = select(UserModel).where(UserModel.id == db_token.user_id)
        user_result = await db.execute(user_query)
        user = user_result.scalar_one_or_none()

        if not user or not user.is_active:
            db_token.is_revoked = True
            db_token.revoked_at = now
            await db.commit()
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="El usuario asociado a la sesión ya no existe o está inactivo.",
                headers={"WWW-Authenticate": "Bearer"},
            )

        # 5. Rotación atómica (RTR)
        db_token.is_revoked = True
        db_token.revoked_at = now

        new_raw_token, new_token_hash = generate_refresh_token_pair()
        new_token_id = uuid.uuid4()
        db_token.replaced_by = new_token_id

        new_db_token = RefreshToken(
            id=new_token_id,
            user_id=user.id,
            tenant_id=user.tenant_id,
            token_hash=new_token_hash,
            family_id=db_token.family_id,  # Mantiene la misma familia de sesión
            is_revoked=False,
            expires_at=now + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS),
            created_at=now,
            client_ip=client_ip,
            user_agent=user_agent,
        )
        db.add(new_db_token)
        await db.commit()

        # 6. Generar nuevo Access Token de 15 minutos
        roles_list = user.roles if isinstance(user.roles, list) else ["RECEPTIONIST"]
        new_access_token = create_access_token(
            subject=str(user.id),
            tenant_id=user.tenant_id,
            roles=roles_list,
        )

        logger.info(f"Token de refresco rotado con éxito para usuario {user.id}. Familia: {db_token.family_id}")
        return new_access_token, new_raw_token, user

    @staticmethod
    async def revoke_session_by_token(db: AsyncSession, raw_refresh_token: str) -> bool:
        """Revoca un token de refresco individual y su familia."""
        token_hash = hash_token(raw_refresh_token)
        query = select(RefreshToken).where(RefreshToken.token_hash == token_hash)
        result = await db.execute(query)
        db_token = result.scalar_one_or_none()

        if not db_token:
            return False

        now = datetime.now(timezone.utc)
        # Revocamos toda la familia asociada
        await db.execute(
            update(RefreshToken)
            .where(RefreshToken.family_id == db_token.family_id)
            .values(is_revoked=True, revoked_at=now)
        )
        await db.commit()
        await token_cache.revoke_family(str(db_token.family_id))
        return True

    @staticmethod
    async def revoke_all_user_sessions(db: AsyncSession, user_id: uuid.UUID) -> int:
        """Invalida forzosamente todas las sesiones de un usuario."""
        now = datetime.now(timezone.utc)
        result = await db.execute(
            update(RefreshToken)
            .where(RefreshToken.user_id == user_id, RefreshToken.is_revoked.is_(False))
            .values(is_revoked=True, revoked_at=now)
        )
        await db.commit()
        return result.rowcount

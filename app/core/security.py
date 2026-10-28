# app/core/security.py
import bcrypt
import hashlib
import secrets
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Optional, Tuple, Union
from jose import jwt, JWTError

from app.core.config import settings

# 🚨 CONFIGURACIÓN GLOBAL DE SEGURIDAD (Validada en config.py)
SECRET_KEY = settings.JWT_SECRET
REFRESH_SECRET_KEY = settings.JWT_REFRESH_SECRET
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = settings.ACCESS_TOKEN_EXPIRE_MINUTES
REFRESH_TOKEN_EXPIRE_DAYS = settings.REFRESH_TOKEN_EXPIRE_DAYS
MFA_PENDING_EXPIRE_MINUTES = settings.MFA_PENDING_EXPIRE_MINUTES


def get_password_hash(password: str) -> str:
    """
    Usa bcrypt nativo directamente para evitar los bugs de passlib en Python 3.13+.
    Pre-hashea con SHA-256 para asegurar una longitud fija de 64 bytes.
    """
    pre_hashed = hashlib.sha256(password.encode("utf-8")).hexdigest()
    password_bytes = pre_hashed.encode("utf-8")
    salt = bcrypt.gensalt()
    hashed = bcrypt.hashpw(password_bytes, salt)
    return hashed.decode("utf-8")


hash_password = get_password_hash


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """
    Verifica la contraseña usando el comparador seguro en tiempo constante de bcrypt.
    """
    try:
        pre_hashed = hashlib.sha256(plain_password.encode("utf-8")).hexdigest()
        return bcrypt.checkpw(
            pre_hashed.encode("utf-8"), 
            hashed_password.encode("utf-8")
        )
    except Exception:
        return False


def hash_token(raw_token: str) -> str:
    """
    Calcula el hash SHA-256 de un token de refresco para almacenamiento seguro en BD.
    Nunca se almacenan tokens de sesión en texto plano.
    """
    return hashlib.sha256(raw_token.strip().encode("utf-8")).hexdigest()


def generate_refresh_token_pair() -> Tuple[str, str]:
    """
    Genera un token de refresco criptográfico de alta entropía (512 bits / 64 bytes URL-safe)
    y su correspondiente hash SHA-256 para persistencia.
    Retorna: (raw_refresh_token, token_hash)
    """
    raw_token = secrets.token_urlsafe(64)
    token_hash = hash_token(raw_token)
    return raw_token, token_hash


def create_access_token(
    subject: Union[str, Any], 
    expires_delta: Optional[timedelta] = None,
    tenant_id: Optional[Union[str, uuid.UUID]] = None,
    roles: Optional[list] = None,
    extra_claims: Optional[Dict[str, Any]] = None,
) -> str:
    """
    Genera un Access Token JWT firmado (HS256) de corta duración (15 minutos por defecto).
    Incluye identificador único jti para posibilitar revocación distribuida.
    """
    now = datetime.now(timezone.utc)
    if expires_delta:
        expire = now + expires_delta
    else:
        expire = now + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    
    to_encode: Dict[str, Any] = {
        "sub": str(subject),
        "iat": int(now.timestamp()),
        "exp": expire,
        "jti": str(uuid.uuid4()),
        "type": "access",
    }
    
    if tenant_id is not None:
        to_encode["tenant_id"] = str(tenant_id)
    if roles is not None:
        to_encode["roles"] = roles
    if extra_claims:
        to_encode.update(extra_claims)
        
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)


def create_mfa_pending_token(
    user_id: Union[str, uuid.UUID],
    tenant_id: Optional[Union[str, uuid.UUID]] = None,
) -> str:
    """
    Genera un token temporal de desafío MFA (10 minutos de vigencia).
    Contiene un scope restringido 'mfa_pending' que NO permite acceso a endpoints normales.
    Solo puede ser consumido por /auth/mfa/challenge.
    """
    now = datetime.now(timezone.utc)
    expire = now + timedelta(minutes=MFA_PENDING_EXPIRE_MINUTES)
    to_encode = {
        "sub": str(user_id),
        "iat": int(now.timestamp()),
        "exp": expire,
        "scope": "mfa_pending",
        "type": "mfa_challenge",
        "jti": str(uuid.uuid4()),
    }
    if tenant_id is not None:
        to_encode["tenant_id"] = str(tenant_id)
        
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)


def decode_token(token: str) -> Dict[str, Any]:
    """
    Decodifica y valida la firma y expiración de un JWT.
    Lanza JWTError si el token es inválido o ha expirado.
    """
    return jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])

# app/core/security.py
from datetime import datetime, timedelta, timezone
import bcrypt
import jwt
from app.core.config import settings

def hash_password(password: str) -> str:
    """Genera un hash seguro usando bcrypt puro (Totalmente compatible con Python 3.13)."""
    pwd_bytes = password.encode('utf-8')
    salt = bcrypt.gensalt()
    hashed = bcrypt.hashpw(pwd_bytes, salt)
    return hashed.decode('utf-8')

def verify_password(password: str, hashed: str) -> bool:
    """Verifica si la contraseña en texto plano coincide con el hash guardado."""
    try:
        return bcrypt.checkpw(
            password.encode('utf-8'), 
            hashed.encode('utf-8')
        )
    except Exception:
        return False

def create_access_token(data: dict) -> str:
    """Genera un Access Token JWT usando la configuración global del sistema."""
    payload = data.copy()
    expire = datetime.now(timezone.utc) + timedelta(
        minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES
    )
    payload.update({"exp": expire})
    return jwt.encode(payload, settings.JWT_SECRET, algorithm="HS256")

def create_refresh_token(data: dict) -> str:
    """Genera un Refresh Token JWT para permitir la renovación de sesiones."""
    payload = data.copy()
    expire = datetime.now(timezone.utc) + timedelta(
        days=settings.REFRESH_TOKEN_EXPIRE_DAYS
    )
    payload.update({"exp": expire})
    return jwt.encode(payload, settings.JWT_REFRESH_SECRET, algorithm="HS256")
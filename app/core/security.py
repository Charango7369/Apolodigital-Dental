# app/core/security.py
import os
from datetime import datetime, timedelta, timezone
from typing import Any, Union
from jose import jwt
from passlib.context import CryptContext
import hashlib

# 🚨 CONFIGURACIÓN GLOBAL DE SEGURIDAD
SECRET_KEY = os.getenv("JWT_SECRET_KEY", "SUPER_SECRET_STRING_PARA_APOLO_DENTAL_2026")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60 * 24  # El token durará 24 horas

# Motor de hashing para los strings fijos generados por SHA-256
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

def get_password_hash(password: str) -> str:
    """
    Convierte cualquier longitud de contraseña a un string fijo de 64 caracteres
    vía SHA-256 para evadir el límite de 72 bytes de Bcrypt, y luego aplica el hash.
    """
    pre_hashed = hashlib.sha256(password.encode("utf-8")).hexdigest()
    return pwd_context.hash(pre_hashed)

# 🔗 ALIAS DE COMPATIBILIDAD CON USER-SERVICE
hash_password = get_password_hash

def verify_password(plain_password: str, hashed_password: str) -> bool:
    """
    Pre-hashea la contraseña entrante en texto plano para compararla 
    con el formato seguro almacenado en la base de datos.
    """
    pre_hashed = hashlib.sha256(plain_password.encode("utf-8")).hexdigest()
    return pwd_context.verify(pre_hashed, hashed_password)

def create_access_token(subject: Union[str, Any], expires_delta: timedelta = None) -> str:
    """
    Genera un token JWT firmado para el control de sesiones de la API.
    """
    if expires_delta:
        expire = datetime.now(timezone.utc) + expires_delta
    else:
        expire = datetime.now(timezone.utc) + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    
    to_encode = {"exp": expire, "sub": str(subject)}
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt


# app/core/security.py
import os
import bcrypt
import hashlib
from datetime import datetime, timedelta, timezone
from typing import Any, Union
from jose import jwt

# 🚨 CONFIGURACIÓN GLOBAL DE SEGURIDAD
SECRET_KEY = os.getenv("JWT_SECRET_KEY", "SUPER_SECRET_STRING_PARA_APOLO_DENTAL_2026")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60 * 24  # El token durará 24 horas

def get_password_hash(password: str) -> str:
    """
    Usa bcrypt nativo directamente para evitar los bugs de passlib en Python 3.13.
    Pre-hashea con SHA-256 para asegurar una longitud fija de 64 bytes.
    """
    # 1. Forzamos que cualquier texto mida exactamente 64 caracteres hex
    pre_hashed = hashlib.sha256(password.encode("utf-8")).hexdigest()
    # 2. Convertimos a bytes para el binario de bcrypt
    password_bytes = pre_hashed.encode("utf-8")
    # 3. Generamos la sal y hasheamos de forma nativa
    salt = bcrypt.gensalt()
    hashed = bcrypt.hashpw(password_bytes, salt)
    # 4. Devolvemos string limpio para Postgres
    return hashed.decode("utf-8")

# 🔗 ALIAS PARA TU USER-SERVICE
hash_password = get_password_hash

def verify_password(plain_password: str, hashed_password: str) -> bool:
    """
    Verifica la contraseña usando el comparador seguro de la librería nativa.
    """
    try:
        pre_hashed = hashlib.sha256(plain_password.encode("utf-8")).hexdigest()
        return bcrypt.checkpw(
            pre_hashed.encode("utf-8"), 
            hashed_password.encode("utf-8")
        )
    except Exception:
        return False

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
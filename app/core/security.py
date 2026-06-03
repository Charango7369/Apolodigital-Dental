# app/core/security.py
import os
from datetime import datetime, timedelta, timezone
from typing import Any, Union
from jose import jwt
from passlib.context import CryptContext

# 🚨 LAS DOS VARIABLES QUE EXIGE EL ERROR:
SECRET_KEY = os.getenv("JWT_SECRET_KEY", "SUPER_SECRET_STRING_PARA_APOLO_DENTAL_2026")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60 * 24  # El token durará 24 horas

# Configuración del hashing de contraseñas
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# app/core/security.py

# ... (todo tu código anterior se queda exactamente igual) ...

def get_password_hash(password: str) -> str:
    return pwd_context.hash(password)

# 🔗 ALIAS DE COMPATIBILIDAD:
# Esto mapea el nombre que tu UserService ya está buscando
hash_password = get_password_hash

def verify_password(plain_password: str, hashed_password: str) -> bool:
    return pwd_context.verify(plain_password, hashed_password)

# ... (el resto del archivo se queda igual) ...

# 🔓 Verificar si la contraseña coincide con el hash de la DB
def verify_password(plain_password: str, hashed_password: str) -> bool:
    return pwd_context.verify(plain_password, hashed_password)

# 🎫 Crear el Token JWT para el usuario logueado
def create_access_token(subject: Union[str, Any], expires_delta: timedelta = None) -> str:
    if expires_delta:
        expire = datetime.now(timezone.utc) + expires_delta
    else:
        expire = datetime.now(timezone.utc) + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    
    to_encode = {"exp": expire, "sub": str(subject)}
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt
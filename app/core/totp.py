# app/core/totp.py
"""
Implementación nativa de MFA TOTP según RFC 6238 y RFC 4226.
Provee compatibilidad estricta con aplicaciones de autenticación estándar:
Google Authenticator, Microsoft Authenticator, Authy, Apple Keychain y 1Password.
Sin dependencias externas propensas a fallos de compilación C en Windows.
"""
import base64
import hashlib
import hmac
import secrets
import struct
import time
from urllib.parse import quote


def generate_totp_secret(length_bytes: int = 20) -> str:
    """
    Genera un secreto criptográfico de 160 bits (20 bytes) codificado en Base32 (sin padding),
    según la recomendación de seguridad de RFC 4226 / RFC 6238.
    """
    random_bytes = secrets.token_bytes(length_bytes)
    return base64.b32encode(random_bytes).decode("ascii").rstrip("=")


def _normalize_secret(secret: str) -> bytes:
    """Decodifica un secreto Base32 manejando espaciados y padding faltante."""
    clean_secret = secret.strip().replace(" ", "").upper()
    padding_needed = (8 - (len(clean_secret) % 8)) % 8
    clean_secret += "=" * padding_needed
    return base64.b32decode(clean_secret, casefold=True)


def get_totp_code(secret: str, timestamp: int | None = None, time_step_seconds: int = 30) -> str:
    """
    Calcula el código TOTP de 6 dígitos para un secreto y timestamp dados.
    """
    if timestamp is None:
        timestamp = int(time.time())
    
    counter = timestamp // time_step_seconds
    key = _normalize_secret(secret)
    # Empaquetar contador en formato big-endian uint64 (RFC 4226)
    msg = struct.pack(">Q", counter)
    
    # HMAC-SHA1
    digest = hmac.new(key, msg, hashlib.sha1).digest()
    
    # Truncamiento dinámico (Dynamic Truncation)
    offset = digest[-1] & 0x0F
    code_int = struct.unpack(">I", digest[offset:offset + 4])[0] & 0x7FFFFFFF
    
    code = code_int % 1_000_000
    return f"{code:06d}"


def verify_totp(secret: str, code: str, window: int = 1, time_step_seconds: int = 30) -> bool:
    """
    Verifica un código TOTP contra el secreto.
    - Soporta ventana de tolerancia para compensar desincronización de reloj (por defecto +-1 paso = 30s).
    - Utiliza comparación en tiempo constante (hmac.compare_digest) contra timing attacks.
    """
    if not secret or not code:
        return False
    
    clean_code = str(code).strip()
    if len(clean_code) != 6 or not clean_code.isdigit():
        return False
    
    current_time = int(time.time())
    current_step = current_time // time_step_seconds
    
    try:
        for offset in range(-window, window + 1):
            target_step = current_step + offset
            target_time = target_step * time_step_seconds
            expected_code = get_totp_code(secret, timestamp=target_time, time_step_seconds=time_step_seconds)
            if hmac.compare_digest(expected_code, clean_code):
                return True
    except Exception:
        return False
        
    return False


def generate_totp_uri(secret: str, account_name: str, issuer: str = "Dental SaaS") -> str:
    """
    Construye el URI estándar 'otpauth://' listo para generación de códigos QR
    y enlace de configuración rápida con Google/MS Authenticator.
    """
    clean_secret = secret.strip().replace(" ", "").upper()
    label = f"{quote(issuer)}:{quote(account_name)}"
    return (
        f"otpauth://totp/{label}?"
        f"secret={clean_secret}&"
        f"issuer={quote(issuer)}&"
        f"algorithm=SHA1&"
        f"digits=6&"
        f"period=30"
    )

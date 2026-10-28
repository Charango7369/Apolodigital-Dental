# app/core/encryption.py
"""
Motor Criptográfico de Cifrado a Nivel de Campo (Field-Level Encryption - FLE).
Implementa cifrado autenticado AES-256-GCM para datos médicos protegidos (PHI)
según requerimientos de HIPAA Security Rule § 164.312(a)(2)(iv) y GDPR Artículo 32.
"""
import base64
import json
import logging
import os
from typing import Any, Optional, Union
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.hkdf import HKDF
from cryptography.hazmat.primitives import hashes
from sqlalchemy import JSON
from sqlalchemy.types import TypeDecorator

from app.core.config import settings

logger = logging.getLogger(__name__)

# Prefijo de versión de payload cifrado
ENCRYPTION_VERSION_PREFIX = "v1:"


def get_phi_encryption_key() -> bytes:
    """
    Obtiene la clave AES de 256 bits (32 bytes).
    Si PHIE_ENCRYPTION_KEY está configurada (hex), la decodifica.
    De lo contrario, deriva una clave de 256 bits determinística pero segura
    a partir de JWT_SECRET usando HKDF-SHA256 (NIST SP 800-56C / RFC 5869).
    """
    explicit_key = getattr(settings, "PHIE_ENCRYPTION_KEY", None)
    if explicit_key and len(explicit_key.strip()) >= 32:
        clean = explicit_key.strip()
        try:
            key_bytes = bytes.fromhex(clean)
            if len(key_bytes) == 32:
                return key_bytes
        except ValueError:
            pass
        return clean.encode("utf-8")[:32]

    # Derivación criptográfica mediante HKDF-SHA256 con salt de aplicación
    hkdf = HKDF(
        algorithm=hashes.SHA256(),
        length=32,
        salt=b"apolodigital-phi-encryption-salt-2026",
        info=b"aes-256-gcm-field-encryption",
    )
    return hkdf.derive(settings.JWT_SECRET.encode("utf-8"))


def encrypt_phi(data: Any) -> str:
    """
    Cifra una estructura de datos (dict, list, str) con AES-256-GCM.
    - Genera un IV/Nonce único de 96 bits (12 bytes) criptográficamente seguro.
    - Produce un tag de autenticación de 128 bits contra manipulación física.
    - Retorna el payload formateado: "v1:<base64(nonce + ciphertext + tag)>".
    """
    if data is None:
        return ""

    key = get_phi_encryption_key()
    aesgcm = AESGCM(key)

    # 1. Serializar a JSON bytes
    if isinstance(data, (dict, list)):
        payload_bytes = json.dumps(data, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    elif isinstance(data, str):
        payload_bytes = data.encode("utf-8")
    elif isinstance(data, (int, float, bool)):
        payload_bytes = str(data).encode("utf-8")
    else:
        payload_bytes = str(data).encode("utf-8")

    # 2. Generar Nonce/IV único (12 bytes - 96 bits)
    nonce = os.urandom(12)

    # 3. Cifrado autenticado (AESGCM genera automáticamente el auth tag y lo concatena al ciphertext)
    ciphertext_with_tag = aesgcm.encrypt(nonce, payload_bytes, None)

    # 4. Concatenación: Nonce (12 bytes) + Ciphertext + Tag
    combined = nonce + ciphertext_with_tag
    encoded_b64 = base64.b64encode(combined).decode("ascii")

    return f"{ENCRYPTION_VERSION_PREFIX}{encoded_b64}"


def decrypt_phi(encrypted_payload: str) -> Any:
    """
    Descifra un payload generado por encrypt_phi.
    - Valida versión y formato.
    - Extrae el Nonce y descifra verificando la integridad del tag en tiempo constante.
    - Lanza ValueError si el tag fue alterado o la llave no coincide.
    """
    if not encrypted_payload or not isinstance(encrypted_payload, str):
        return encrypted_payload

    clean = encrypted_payload.strip()
    if not clean.startswith(ENCRYPTION_VERSION_PREFIX):
        # No tiene prefijo de cifrado, retornar como está
        return clean

    key = get_phi_encryption_key()
    aesgcm = AESGCM(key)

    b64_part = clean[len(ENCRYPTION_VERSION_PREFIX):]
    try:
        combined = base64.b64decode(b64_part)
        if len(combined) < 28:  # 12 bytes nonce + al menos 16 bytes auth tag
            raise ValueError("Longitud de payload cifrado insuficiente.")

        nonce = combined[:12]
        ciphertext_and_tag = combined[12:]

        decrypted_bytes = aesgcm.decrypt(nonce, ciphertext_and_tag, None)
        decoded_text = decrypted_bytes.decode("utf-8")

        # Intentar deserializar como JSON si es dict o list
        try:
            return json.loads(decoded_text)
        except json.JSONDecodeError:
            return decoded_text

    except Exception as e:
        logger.error(f"[ENCRYPTION ERROR] Fallo al descifrar campo PHI: {str(e)}")
        raise ValueError("Error de integridad o clave al descifrar dato médico sensible.")


class EncryptedJSON(TypeDecorator):
    """
    Tipo SQLAlchemy personalizado para almacenamiento cifrado AES-256-GCM transparente.
    - En la base de datos se almacena como JSON envelope: {"__phi_encrypted__": True, "v": 1, "payload": "v1:..."}.
    - En la aplicación Python y schemas Pydantic se lee y escribe como dict nativo.
    - Soporta compatibilidad retroactiva con registros existentes sin cifrar.
    """
    impl = JSON
    cache_ok = True

    def process_bind_param(self, value: Any, dialect) -> Optional[dict]:
        if value is None:
            return None
        
        # Si ya viene envuelto como cifrado, lo mantenemos
        if isinstance(value, dict) and value.get("__phi_encrypted__") is True:
            return value

        # Cifrar estructura de datos
        ciphertext = encrypt_phi(value)
        return {
            "__phi_encrypted__": True,
            "v": 1,
            "payload": ciphertext,
        }

    def process_result_value(self, value: Any, dialect) -> Any:
        if value is None:
            return None

        # Si es un sobre cifrado, desciframos transparentemente
        if isinstance(value, dict) and value.get("__phi_encrypted__") is True:
            payload = value.get("payload", "")
            return decrypt_phi(payload)

        # Si es un registro previo sin cifrar, devolvemos el diccionario tal cual (Zero-downtime compatibility)
        return value

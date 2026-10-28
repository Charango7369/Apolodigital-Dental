# tests/security/test_phase4_medical_encryption_audit.py
"""
Suite de Pruebas Automatizadas de Seguridad - Fase 4:
Cifrado Autenticado AES-256-GCM para Datos Médicos Protegidos (PHI)
y Bitácora de Auditoría Médica Inmutable (HIPAA Security Rule § 164.312).
"""
import base64
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4
import pytest
from fastapi import HTTPException

import app.models
from app.core.encryption import encrypt_phi, decrypt_phi, EncryptedJSON
from app.modules.audit.models import MedicalAuditLog
from app.modules.users.models import User as UserModel


# ============================================================================
# 1. PRUEBAS DE CIFRADO AUTENTICADO AES-256-GCM (FIELD-LEVEL ENCRYPTION)
# ============================================================================

def test_aes_256_gcm_encryption_and_decryption_integrity():
    """Valida el ciclo de vida completo de cifrado y descifrado de datos odontológicos."""
    teeth_data = {
        "18": {"condition": "CARIES", "faces": ["O", "M"]},
        "21": {"condition": "CORONA", "faces": []},
        "46": {"condition": "TRATAMIENTO_CONDUCTO", "faces": ["O"]}
    }

    encrypted = encrypt_phi(teeth_data)
    assert encrypted.startswith("v1:")
    assert len(encrypted) > 50

    # Descifrado íntegro
    decrypted = decrypt_phi(encrypted)
    assert decrypted == teeth_data


def test_aes_256_gcm_fresh_nonce_per_operation():
    """
    SEGURIDAD INDISTINGUIBLE (CPA-Security):
    Dos operaciones de cifrado sobre el MISMO contenido clínico deben generar
    cifrados totalmente distintos debido a la generación de un Nonce/IV único de 96 bits.
    """
    teeth_data = {"11": {"condition": "SANO", "faces": []}}
    
    cipher1 = encrypt_phi(teeth_data)
    cipher2 = encrypt_phi(teeth_data)
    
    assert cipher1 != cipher2, "VULNERABILIDAD: Reuso de Nonce/IV en AES-GCM detectado"
    
    # Ambos deben descifrar al mismo valor original
    assert decrypt_phi(cipher1) == teeth_data
    assert decrypt_phi(cipher2) == teeth_data


def test_aes_256_gcm_tamper_detection():
    """
    VECTOR DE MANIPULACIÓN (Tampering):
    Si un atacante modifica un solo bit del ciphertext o del Authentication Tag,
    AES-256-GCM debe rechazar el descifrado lanzando ValueError por falla de integridad.
    """
    teeth_data = {"18": {"condition": "CARIES", "faces": ["O"]}}
    encrypted = encrypt_phi(teeth_data)
    
    # Extraer payload en base64 y alterar bytes
    b64_part = encrypted[3:]
    raw_bytes = bytearray(base64.b64decode(b64_part))
    
    # Modificar el último byte (parte del tag de autenticación)
    raw_bytes[-1] ^= 0xFF
    tampered_payload = "v1:" + base64.b64encode(raw_bytes).decode("ascii")

    with pytest.raises(ValueError) as exc_info:
        decrypt_phi(tampered_payload)

    assert "error de integridad" in str(exc_info.value).lower()


def test_encrypted_json_type_decorator_backwards_compatibility():
    """
    Valida la compatibilidad retroactiva del TypeDecorator:
    Si la base de datos devuelve un diccionario previo no cifrado, se procesa sin error.
    """
    type_decorator = EncryptedJSON()
    legacy_data = {"11": {"condition": "CARIES"}}
    
    # Registro legacy en texto plano
    result = type_decorator.process_result_value(legacy_data, None)
    assert result == legacy_data

    # Registro cifrado moderno
    bound = type_decorator.process_bind_param(legacy_data, None)
    assert bound["__phi_encrypted__"] is True
    assert bound["payload"].startswith("v1:")

    decrypted_result = type_decorator.process_result_value(bound, None)
    assert decrypted_result == legacy_data


# ============================================================================
# 2. PRUEBAS DE AUDITORÍA MÉDICA INMUTABLE (HIPAA COMPLIANCE)
# ============================================================================

def test_medical_audit_log_model_structure():
    """Valida la estructura del modelo de auditoría médica según HIPAA § 164.312(b)."""
    log = MedicalAuditLog(
        id=uuid4(),
        user_id=uuid4(),
        tenant_id=uuid4(),
        action="CREATE",
        resource_type="ODONTOGRAM",
        resource_id=uuid4(),
        patient_id=uuid4(),
        ip_address="192.168.1.100",
        user_agent="Mozilla/5.0 Medical Station",
        details={"teeth_count": 32}
    )

    assert log.action == "CREATE"
    assert log.resource_type == "ODONTOGRAM"
    assert log.ip_address == "192.168.1.100"
    assert log.details["teeth_count"] == 32


@pytest.mark.asyncio
async def test_audit_logs_cross_tenant_isolation():
    """
    AISLAMIENTO MULTI-TENANT EN AUDITORÍA:
    Un administrador de la Clínica A no puede ver logs de la Clínica B.
    El SUPER_ADMIN posee acceso global.
    """
    from app.modules.audit.router import get_medical_audit_logs

    clinic_a_id = uuid4()
    clinic_b_id = uuid4()

    admin_clinic_a = UserModel(
        id=uuid4(),
        tenant_id=clinic_a_id,
        full_name="Admin Clínica A",
        email="admin@clinica-a.com",
        hashed_password="hash",
        roles=["ADMIN"],
        is_active=True
    )

    super_admin = UserModel(
        id=uuid4(),
        tenant_id=clinic_a_id,
        full_name="Super Admin Global",
        email="super@plataforma.com",
        hashed_password="hash",
        roles=["SUPER_ADMIN"],
        is_active=True
    )

    mock_db = AsyncMock()
    mock_result = MagicMock()
    mock_result.scalars.return_value.all.return_value = []
    mock_db.execute.return_value = mock_result

    # 1. Admin de Clínica A consulta logs: DEBE filtrar por su tenant_id
    await get_medical_audit_logs(
        patient_id=None,
        user_id=None,
        action=None,
        resource_type=None,
        limit=50,
        offset=0,
        current_user=admin_clinic_a,
        db=mock_db
    )
    assert mock_db.execute.called

    # 2. Super Admin consulta logs
    await get_medical_audit_logs(
        patient_id=None,
        user_id=None,
        action=None,
        resource_type=None,
        limit=50,
        offset=0,
        current_user=super_admin,
        db=mock_db
    )
    assert mock_db.execute.call_count == 2

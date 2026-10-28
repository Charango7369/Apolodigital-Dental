# tests/security/test_vuln_04_bola_isolation.py
import pytest
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4
from fastapi import HTTPException

# Cargar registro global de modelos SQLAlchemy
import app.models
from app.shared.dependencies import get_current_tenant_id, verify_tenant_entity
from app.modules.users.models import User as UserModel
from app.modules.patients.models import Patient as PatientModel


@pytest.mark.asyncio
async def test_get_current_tenant_id_success():
    """Valida la extracción del tenant_id del usuario autenticado."""
    tenant_id = uuid4()
    user = UserModel(
        id=uuid4(),
        full_name="Dr. Test",
        email="doctor@test.com",
        hashed_password="hash",
        roles=["DOCTOR"],
        tenant_id=tenant_id,
        is_active=True
    )
    extracted = await get_current_tenant_id(current_user=user)
    assert extracted == tenant_id


@pytest.mark.asyncio
async def test_get_current_tenant_id_denies_unassigned_tenant():
    """Valida Default Deny si un usuario no posee tenant asignado."""
    user = UserModel(
        id=uuid4(),
        full_name="Usuario Huérfano",
        email="huerfano@test.com",
        hashed_password="hash",
        roles=["RECEPTIONIST"],
        tenant_id=None,
        is_active=True
    )
    with pytest.raises(HTTPException) as exc:
        await get_current_tenant_id(current_user=user)
    assert exc.value.status_code == 403


@pytest.mark.asyncio
async def test_verify_tenant_entity_blocks_cross_tenant_access():
    """
    VECTOR BOLA / IDOR:
    Si una clínica intenta acceder a una entidad (ej. paciente) de otra clínica,
    verify_tenant_entity debe responder con HTTP 404 (previniendo enumeración).
    """
    mock_db = AsyncMock()
    mock_result = MagicMock()
    # Simula que la consulta WHERE id == x AND tenant_id == y no encuentra registros
    mock_result.scalar_one_or_none.return_value = None
    mock_db.execute.return_value = mock_result

    clinic_a_tenant = uuid4()
    clinic_b_patient_id = uuid4()

    with pytest.raises(HTTPException) as exc:
        await verify_tenant_entity(
            db=mock_db,
            model=PatientModel,
            entity_id=clinic_b_patient_id,
            tenant_id=clinic_a_tenant,
            entity_name="Paciente"
        )

    assert exc.value.status_code == 404
    assert "no encontrado en esta clínica" in exc.value.detail


@pytest.mark.asyncio
async def test_verify_tenant_entity_grants_access_to_owned_resource():
    """Valida que una consulta legítima dentro del mismo tenant devuelva la entidad."""
    tenant_id = uuid4()
    patient_id = uuid4()
    dummy_patient = PatientModel(id=patient_id, tenant_id=tenant_id, first_name="Juan", last_name="Pérez")

    mock_db = AsyncMock()
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = dummy_patient
    mock_db.execute.return_value = mock_result

    entity = await verify_tenant_entity(
        db=mock_db,
        model=PatientModel,
        entity_id=patient_id,
        tenant_id=tenant_id,
        entity_name="Paciente"
    )
    assert entity.id == patient_id

# tests/security/test_vuln_06_rbac_matrix.py
import pytest
from uuid import uuid4
from fastapi import HTTPException
from app.modules.auth.dependencies import require_role
from app.modules.users.models import User as UserModel


@pytest.fixture
def make_user():
    def _factory(roles: list, tenant_id=None):
        return UserModel(
            id=uuid4(),
            full_name="Usuario Test",
            email="test@example.com",
            hashed_password="hash",
            roles=roles,
            tenant_id=tenant_id or uuid4(),
            is_active=True
        )
    return _factory


@pytest.mark.asyncio
async def test_receptionist_denied_admin_endpoint(make_user):
    """Valida que un RECEPTIONIST no pueda acceder a endpoints restringidos a ADMIN."""
    receptionist = make_user(roles=["RECEPTIONIST"])
    admin_checker = require_role(["ADMIN"])

    with pytest.raises(HTTPException) as exc:
        await admin_checker(current_user=receptionist)

    assert exc.value.status_code == 403
    assert "Acceso denegado" in exc.value.detail


@pytest.mark.asyncio
async def test_doctor_denied_admin_endpoint(make_user):
    """Valida que un DOCTOR no pueda acceder a configuración o reportes de ADMIN."""
    doctor = make_user(roles=["DOCTOR"])
    admin_checker = require_role(["ADMIN"])

    with pytest.raises(HTTPException) as exc:
        await admin_checker(current_user=doctor)

    assert exc.value.status_code == 403


@pytest.mark.asyncio
async def test_admin_granted_admin_endpoint(make_user):
    """Valida que un ADMIN acceda correctamente a endpoints administrativos."""
    admin = make_user(roles=["ADMIN"])
    admin_checker = require_role(["ADMIN"])

    result = await admin_checker(current_user=admin)
    assert result.id == admin.id


@pytest.mark.asyncio
async def test_super_admin_bypasses_clinical_restriction(make_user):
    """Valida que SUPER_ADMIN tenga acceso universal sobre endpoints clínicos."""
    super_admin = make_user(roles=["SUPER_ADMIN"])
    doctor_checker = require_role(["DOCTOR"])

    result = await doctor_checker(current_user=super_admin)
    assert result.id == super_admin.id


@pytest.mark.asyncio
async def test_default_deny_when_roles_empty(make_user):
    """Valida Default Deny: si un usuario no tiene roles o arreglo vacío, se deniega."""
    empty_user = make_user(roles=[])
    receptionist_checker = require_role(["RECEPTIONIST"])

    with pytest.raises(HTTPException) as exc:
        await receptionist_checker(current_user=empty_user)

    assert exc.value.status_code == 403

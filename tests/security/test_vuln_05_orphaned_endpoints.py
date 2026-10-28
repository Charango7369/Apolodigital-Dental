# tests/security/test_vuln_05_orphaned_endpoints.py
import pytest
from io import BytesIO
from uuid import uuid4
from fastapi import UploadFile, HTTPException

from app.modules.files.router import upload_file, ALLOWED_EXTENSIONS, ALLOWED_MIME_TYPES
from app.modules.users.models import User as UserModel


@pytest.fixture
def test_user():
    return UserModel(
        id=uuid4(),
        full_name="Dr. Archivos",
        email="archivos@dental.com",
        hashed_password="hash",
        roles=["DOCTOR"],
        tenant_id=uuid4(),
        is_active=True
    )


@pytest.mark.asyncio
async def test_file_upload_blocks_unauthorized_extensions(test_user):
    """VECTOR RCE / SCRIPT INJECTION: Rechaza scripts ejecutables (.php, .exe, .sh, .py)."""
    malicious_file = UploadFile(
        file=BytesIO(b"<?php system($_GET['cmd']); ?>"),
        filename="backdoor.php",
        headers={"content-type": "application/x-php"}
    )

    with pytest.raises(HTTPException) as exc:
        await upload_file(file=malicious_file, current_user=test_user)

    assert exc.value.status_code == 415
    assert "Tipo de archivo no permitido" in exc.value.detail


@pytest.mark.asyncio
async def test_file_upload_blocks_oversized_payloads(test_user):
    """VECTOR DoS: Rechaza archivos que superen 10 MB."""
    oversized_data = b"0" * (10 * 1024 * 1024 + 1024)
    big_file = UploadFile(
        file=BytesIO(oversized_data),
        filename="radiografia_enorme.pdf",
        headers={"content-type": "application/pdf"}
    )

    with pytest.raises(HTTPException) as exc:
        await upload_file(file=big_file, current_user=test_user)

    assert exc.value.status_code == 413
    assert "excede el tamaño máximo" in exc.value.detail


@pytest.mark.asyncio
async def test_file_upload_sanitizes_path_traversal(test_user):
    """VECTOR PATH TRAVERSAL: Sanitiza nombres como ../../../etc/passwd."""
    traversal_file = UploadFile(
        file=BytesIO(b"%PDF-1.4 test document content"),
        filename="../../../../radiografia_segura.pdf",
        headers={"content-type": "application/pdf"}
    )

    res = await upload_file(file=traversal_file, current_user=test_user)
    assert res["success"] is True
    assert res["filename"] == "radiografia_segura.pdf"
    assert ".." not in res["filename"]
    assert res["tenant_id"] == str(test_user.tenant_id)

# app/modules/files/router.py
from pathlib import Path
from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File
from typing import List

from app.modules.auth.dependencies import get_current_user
from app.modules.users.models import User as UserModel

router = APIRouter(prefix="/files", tags=["Files"])

# Configuración defensiva de carga de archivos médicos
ALLOWED_MIME_TYPES = {
    "image/png",
    "image/jpeg",
    "image/webp",
    "application/pdf",
    "application/dicom",
}
ALLOWED_EXTENSIONS = {".png", ".jpg", ".jpeg", ".webp", ".pdf", ".dcm"}
MAX_FILE_SIZE_BYTES = 10 * 1024 * 1024  # 10 MB


@router.post("/upload")
async def upload_file(
    file: UploadFile = File(...),
    current_user: UserModel = Depends(get_current_user),
):
    """
    Subida segura de archivos médicos (radiografías, fotos clínicas, documentos PDF).
    Valida extensión, Content-Type, tamaño y sanitiza el nombre de archivo.
    """
    original_filename = file.filename or "archivo_sin_nombre"
    sanitized_filename = Path(original_filename).name  # Prevenir Path Traversal

    extension = Path(sanitized_filename).suffix.lower()
    if extension not in ALLOWED_EXTENSIONS or file.content_type not in ALLOWED_MIME_TYPES:
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail=f"Tipo de archivo no permitido ({extension}). Formatos aceptados: PDF, PNG, JPG, WEBP, DICOM.",
        )

    # Validar tamaño del archivo en streaming
    contents = await file.read()
    if len(contents) > MAX_FILE_SIZE_BYTES:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail="El archivo excede el tamaño máximo permitido de 10 MB.",
        )

    return {
        "success": True,
        "filename": sanitized_filename,
        "content_type": file.content_type,
        "size_bytes": len(contents),
        "tenant_id": str(current_user.tenant_id),
        "uploaded_by": str(current_user.id),
        "status": "validated_and_ready",
    }


@router.get("/")
async def list_files(current_user: UserModel = Depends(get_current_user)):
    """
    Lista archivos vinculados al tenant del usuario autenticado.
    """
    return {
        "success": True,
        "tenant_id": str(current_user.tenant_id),
        "files": [],
    }

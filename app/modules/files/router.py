from fastapi import APIRouter, UploadFile, File
from typing import List

router = APIRouter(prefix="/files", tags=["Files"])

@router.post("/upload")
async def upload_file(file: UploadFile = File(...)):
    return {
        "filename": file.filename,
        "content_type": file.content_type,
        "status": "uploaded"
    }

@router.get("/")
async def list_files():
    return {"files": []}
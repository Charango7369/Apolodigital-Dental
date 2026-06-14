# app/modules/whatsapp/schemas.py
from pydantic import BaseModel
from typing import Optional

class QRCodeResponse(BaseModel):
    instance_name: str
    qr_code_base64: Optional[str] = None
    status: str
    message: str

class ConnectionStatusResponse(BaseModel):
    instance_name: str
    status: str # Ej: "CONNECTED", "DISCONNECTED", "PENDING_QR"
    phone_connected: Optional[str] = None
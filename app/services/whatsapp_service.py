# app/services/whatsapp_service.py
import logging
from typing import Dict, Any, Optional
from app.services.whatsapp_cloud import whatsapp_cloud

logger = logging.getLogger(__name__)

class WhatsAppService:
    def __init__(self):
        self.api_url = "http://tu-servidor-evolution-api:8080"
        self.global_api_key = "16ZLi2PdqSmFVikmykpQ"

    async def send_message(self, instance_name: str, phone: str, text: str) -> Dict[str, Any]:
        """
        Envío de mensaje por WhatsApp.
        Intenta enviar a través del servicio oficial de WhatsApp Cloud API.
        """
        logger.info(f"[WHATSAPP] Envío solicitado para instancia {instance_name} al teléfono {phone}")
        return await whatsapp_cloud.send_text_message(to_phone=phone, text=text)

    async def create_instance(self, instance_name: str) -> Dict[str, Any]:
        return {"status": "SUCCESS", "message": "Instancia creada"}

    async def get_qr(self, instance_name: str) -> Dict[str, Any]:
        return {
            "status": "PENDING_QR", 
            "base64": "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8BQDwAEhQGAhKmMIQAAAABJRU5ErkJggg==" 
        }

    async def get_status(self, instance_name: str) -> str:
        return "CONNECTED" if whatsapp_cloud.is_configured else "MOCK_CONNECTED"

    async def logout(self, instance_name: str) -> bool:
        return True

# Instancia global para usar en tus routers
wa_service = WhatsAppService()

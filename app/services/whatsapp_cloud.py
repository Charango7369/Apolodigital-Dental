# app/services/whatsapp_cloud.py
import logging
from typing import Dict, Any, Optional
import httpx
from app.core.config import settings

logger = logging.getLogger(__name__)

class WhatsAppCloudService:
    """
    Servicio de integración con WhatsApp Cloud API oficial (Meta Graph API).
    Soporta envío de mensajes de texto libres y plantillas aprobadas (templates)
    para recordatorios automáticos de citas y alertas clínicas.
    """
    def __init__(self):
        self.phone_number_id = settings.WHATSAPP_PHONE_NUMBER_ID
        self.access_token = settings.WHATSAPP_ACCESS_TOKEN
        self.api_version = getattr(settings, "WHATSAPP_API_VERSION", "v20.0")
        self.base_url = f"https://graph.facebook.com/{self.api_version}"

    @property
    def is_configured(self) -> bool:
        return bool(self.phone_number_id and self.access_token)

    def _sanitize_phone(self, phone: str) -> str:
        """Limpia el número telefónico para formato E.164 sin signos + ni espacios."""
        return "".join(c for c in phone if c.isdigit())

    async def send_text_message(self, to_phone: str, text: str) -> Dict[str, Any]:
        """Envía un mensaje de texto simple (dentro de ventana de 24h de conversación)."""
        clean_phone = self._sanitize_phone(to_phone)
        if not self.is_configured:
            logger.warning(
                f"[WHATSAPP CLOUD MOCK] Token o Phone ID no configurado. Mensaje simulado a {clean_phone}: {text[:60]}..."
            )
            return {"status": "MOCK_SENT", "recipient": clean_phone, "text": text}

        url = f"{self.base_url}/{self.phone_number_id}/messages"
        headers = {
            "Authorization": f"Bearer {self.access_token}",
            "Content-Type": "application/json",
        }
        payload = {
            "messaging_product": "whatsapp",
            "recipient_type": "individual",
            "to": clean_phone,
            "type": "text",
            "text": {"preview_url": False, "body": text},
        }

        async with httpx.AsyncClient(timeout=10.0) as client:
            try:
                response = await client.post(url, json=payload, headers=headers)
                response.raise_for_status()
                return response.json()
            except httpx.HTTPStatusError as e:
                logger.error(f"[WHATSAPP CLOUD ERROR] Falló envío a {clean_phone}: {e.response.text}")
                return {"status": "ERROR", "detail": e.response.text}
            except Exception as e:
                logger.error(f"[WHATSAPP CLOUD ERROR] Excepción de conexión: {str(e)}")
                return {"status": "CONNECTION_ERROR", "detail": str(e)}

    async def send_appointment_reminder(
        self,
        to_phone: str,
        patient_name: str,
        date_str: str,
        time_str: str,
        clinic_name: str = "ApoloDigital Dental",
        template_name: str = "recordatorio_cita_dental"
    ) -> Dict[str, Any]:
        """
        Envía plantilla de recordatorio de cita aprobada por Meta:
        Parámetros: {{1}} Paciente, {{2}} Fecha, {{3}} Hora, {{4}} Clínica
        Si la plantilla no está lista o falla, recurre a mensaje directo como fallback.
        """
        clean_phone = self._sanitize_phone(to_phone)

        if not self.is_configured:
            msg = (
                f"🦷 Hola {patient_name}, te recordamos tu cita odontológica en {clinic_name} "
                f"el día {date_str} a las {time_str}. ¡Te esperamos!"
            )
            logger.info(f"[WHATSAPP CLOUD MOCK REMINDER] Enviado a {clean_phone}: {msg}")
            return {"status": "MOCK_REMINDER_SENT", "recipient": clean_phone, "message": msg}

        url = f"{self.base_url}/{self.phone_number_id}/messages"
        headers = {
            "Authorization": f"Bearer {self.access_token}",
            "Content-Type": "application/json",
        }
        payload = {
            "messaging_product": "whatsapp",
            "recipient_type": "individual",
            "to": clean_phone,
            "type": "template",
            "template": {
                "name": template_name,
                "language": {"code": "es"},
                "components": [
                    {
                        "type": "body",
                        "parameters": [
                            {"type": "text", "text": patient_name},
                            {"type": "text", "text": date_str},
                            {"type": "text", "text": time_str},
                            {"type": "text", "text": clinic_name},
                        ],
                    }
                ],
            },
        }

        async with httpx.AsyncClient(timeout=10.0) as client:
            try:
                response = await client.post(url, json=payload, headers=headers)
                response.raise_for_status()
                return response.json()
            except httpx.HTTPStatusError as e:
                logger.warning(
                    f"[WHATSAPP CLOUD] Template falló, intentando mensaje de texto fallback: {e.response.text}"
                )
                fallback_msg = (
                    f"🦷 Estimado/a {patient_name}, le recordamos su cita odontológica en {clinic_name} "
                    f"para el {date_str} a las {time_str}. Por favor confírmenos respondiendo a este mensaje."
                )
                return await self.send_text_message(clean_phone, fallback_msg)


whatsapp_cloud = WhatsAppCloudService()

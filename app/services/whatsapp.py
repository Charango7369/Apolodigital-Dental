# app/services/whatsapp.py

class WhatsAppService:
    def __init__(self, api_url: str, api_token: str):
        self.api_url = api_url
        self.api_token = api_token

    async def send_message(self, phone: str, text: str):
        """
        Método genérico. Hoy usa la API no oficial (QR). 
        Mañana, solo cambias el contenido de esta función para usar la API de Meta.
        """
        # Lógica de petición HTTP (ej. httpx) a tu servidor Evolution API/Baileys
        pass

    async def send_appointment_reminder(self, phone: str, patient_name: str, date: str):
        """
        Plantilla interna para recordatorios de citas.
        """
        text = f"¡Hola {patient_name}! 🦷 Te recordamos tu cita dental para el {date}. Por favor, confírmanos tu asistencia."
        return await self.send_message(phone, text)

# Instanciamos el servicio para importarlo en los routers
wa_service = WhatsAppService(api_url="tu_url_local", api_token="tu_token")
# app/services/whatsapp_service.py
import httpx
from typing import Dict, Any

class WhatsAppService:
    def __init__(self):
        # En el futuro, estas variables vendrán de tu archivo .env
        self.api_url = "http://tu-servidor-evolution-api:8080"
        self.global_api_key = "16ZLi2PdqSmFVikmykpQ"

    async def create_instance(self, instance_name: str) -> Dict[str, Any]:
        """Crea la instancia en el servidor de WhatsApp si no existe."""
        # Lógica real futura:
        # async with httpx.AsyncClient() as client:
        #     response = await client.post(f"{self.api_url}/instance/create", json={"instanceName": instance_name})
        #     return response.json()
        return {"status": "SUCCESS", "message": "Instancia creada"}

    async def get_qr(self, instance_name: str) -> Dict[str, Any]:
        """Obtiene el QR en formato Base64 para el frontend."""
        # Lógica real futura:
        # async with httpx.AsyncClient() as client:
        #     response = await client.get(f"{self.api_url}/instance/connect/{instance_name}")
        #     return response.json() # Retorna el base64
        
        # MOCK para que pruebes tu frontend hoy:
        return {
            "status": "PENDING_QR", 
            "base64": "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8BQDwAEhQGAhKmMIQAAAABJRU5ErkJggg==" 
        }

    async def get_status(self, instance_name: str) -> str:
        """Verifica si el celular ya escaneó el código y está conectado."""
        # Lógica real futura:
        # async with httpx.AsyncClient() as client:
        #     response = await client.get(f"{self.api_url}/instance/connectionState/{instance_name}")
        #     return response.json().get("state")
        return "DISCONNECTED"

    async def logout(self, instance_name: str) -> bool:
        """Desconecta el dispositivo de la clínica."""
        # Lógica real futura: peticion DELETE
        return True

# Instancia global para usar en tus routers
wa_service = WhatsAppService()
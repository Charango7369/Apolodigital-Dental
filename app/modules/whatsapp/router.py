# app/modules/whatsapp/router.py
from fastapi import APIRouter, Depends, HTTPException, status
from app.modules.auth.dependencies import get_current_user, require_role
from app.modules.users.models import User as UserModel
from app.modules.whatsapp.schemas import QRCodeResponse, ConnectionStatusResponse
from app.services.whatsapp_service import wa_service

router = APIRouter(prefix="/whatsapp", tags=["WhatsApp Integration"])

require_admin = require_role(["ADMIN"])


@router.get("/qr", response_model=QRCodeResponse)
async def generate_qr_code(current_user: UserModel = Depends(require_admin)):
    """
    Genera o recupera el código QR para que la clínica vincule su celular.
    Requiere rol ADMIN.
    """
    instance_name = str(current_user.tenant_id)
    
    try:
        # 1. Aseguramos que la instancia exista en el proveedor
        await wa_service.create_instance(instance_name)
        
        # 2. Solicitamos el QR
        qr_data = await wa_service.get_qr(instance_name)
        
        if qr_data.get("status") == "CONNECTED":
            return QRCodeResponse(
                instance_name=instance_name,
                status="CONNECTED",
                message="El dispositivo ya está vinculado. No se requiere QR."
            )
            
        return QRCodeResponse(
            instance_name=instance_name,
            qr_code_base64=qr_data.get("base64"),
            status="PENDING_QR",
            message="Escanea este código QR con el WhatsApp de la clínica."
        )
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error al conectar con el servidor de WhatsApp: {str(e)}"
        )


@router.get("/status", response_model=ConnectionStatusResponse)
async def check_connection_status(current_user: UserModel = Depends(require_admin)):
    """
    Polling de estado de vinculación. Requiere rol ADMIN.
    """
    instance_name = str(current_user.tenant_id)
    try:
        connection_state = await wa_service.get_status(instance_name)
        return ConnectionStatusResponse(
            instance_name=instance_name,
            status=connection_state
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail="Error al verificar el estado")


@router.delete("/disconnect", status_code=status.HTTP_200_OK)
async def disconnect_whatsapp(current_user: UserModel = Depends(require_admin)):
    """
    Cierra la sesión de WhatsApp de la clínica actual. Requiere rol ADMIN.
    """
    instance_name = str(current_user.tenant_id)
    success = await wa_service.logout(instance_name)
    
    if not success:
        raise HTTPException(status_code=400, detail="No se pudo desconectar el dispositivo")
        
    return {"message": "Dispositivo desconectado exitosamente"}

# app/core/audit.py
"""
Servicio Asíncrono de Registro de Auditoría Médica (HIPAA / GDPR).
Garantiza el registro no bloqueante de accesos y modificaciones a registros médicos (PHI)
creando sesiones asíncronas aisladas.
"""
import logging
from datetime import datetime, timezone
from typing import Any, Dict, Optional
from uuid import UUID

from app.db.session import AsyncSessionLocal
from app.modules.audit.models import MedicalAuditLog

logger = logging.getLogger(__name__)


async def record_medical_audit_event(
    user_id: Optional[UUID],
    tenant_id: UUID,
    action: str,
    resource_type: str,
    resource_id: Optional[UUID] = None,
    patient_id: Optional[UUID] = None,
    ip_address: Optional[str] = None,
    user_agent: Optional[str] = None,
    details: Optional[Dict[str, Any]] = None,
) -> None:
    """
    Persiste un registro de auditoría médica de forma asíncrona e independiente.
    Diseñado para ejecutarse como tarea en segundo plano (BackgroundTasks)
    sin degradar la latencia de las consultas clínicas del médico.
    """
    try:
        async with AsyncSessionLocal() as session:
            log_entry = MedicalAuditLog(
                user_id=user_id,
                tenant_id=tenant_id,
                action=action.upper().strip(),
                resource_type=resource_type.upper().strip(),
                resource_id=resource_id,
                patient_id=patient_id,
                timestamp=datetime.now(timezone.utc),
                ip_address=ip_address,
                user_agent=user_agent,
                details=details,
            )
            session.add(log_entry)
            await session.commit()
    except Exception as e:
        # Fallo de auditoría se reporta a logs de alta prioridad sin romper la llamada del usuario
        logger.error(
            f"[AUDIT LOG FAILURE] Error al persistir registro de auditoría médica: {str(e)} | "
            f"user_id={user_id}, tenant={tenant_id}, action={action}, resource={resource_type}"
        )

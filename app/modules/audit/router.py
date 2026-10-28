# app/modules/audit/router.py
import logging
from typing import List, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from app.db.session import get_db
from app.modules.auth.dependencies import require_role
from app.modules.users.models import User as UserModel
from app.modules.audit.models import MedicalAuditLog
from app.modules.audit.schemas import MedicalAuditLogResponse

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/audit", tags=["Audit Logs"])

require_compliance_admin = require_role(["ADMIN", "SUPER_ADMIN"])


@router.get("/medical-logs", response_model=List[MedicalAuditLogResponse])
async def get_medical_audit_logs(
    patient_id: Optional[UUID] = Query(None, description="Filtrar por ID de paciente"),
    user_id: Optional[UUID] = Query(None, description="Filtrar por ID de profesional"),
    action: Optional[str] = Query(None, description="Filtrar por acción (READ, CREATE, UPDATE, DELETE)"),
    resource_type: Optional[str] = Query(None, description="Filtrar por recurso (ODONTOGRAM, PATIENT)"),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    current_user: UserModel = Depends(require_compliance_admin),
    db: AsyncSession = Depends(get_db),
):
    """
    Consulta de Bitácora de Auditoría Médica (Solo Administradores y Auditores de Compliance):
    - Aislamiento Multi-Tenant estricto: Las clínicas solo pueden auditar eventos de su propio tenant.
    - El SUPER_ADMIN posee visibilidad global de la plataforma.
    """
    user_roles = current_user.roles if isinstance(current_user.roles, list) else []
    is_super_admin = "SUPER_ADMIN" in user_roles

    query = select(MedicalAuditLog)

    # 🛡️ Aislamiento por clínica
    if not is_super_admin:
        query = query.where(MedicalAuditLog.tenant_id == current_user.tenant_id)

    if patient_id:
        query = query.where(MedicalAuditLog.patient_id == patient_id)
    if user_id:
        query = query.where(MedicalAuditLog.user_id == user_id)
    if action:
        query = query.where(MedicalAuditLog.action == action.upper().strip())
    if resource_type:
        query = query.where(MedicalAuditLog.resource_type == resource_type.upper().strip())

    query = query.order_by(MedicalAuditLog.timestamp.desc()).offset(offset).limit(limit)

    result = await db.execute(query)
    return result.scalars().all()

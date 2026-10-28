# app/modules/audit/schemas.py
from datetime import datetime
from typing import Optional, Dict, Any
from uuid import UUID
from pydantic import BaseModel, ConfigDict


class MedicalAuditLogResponse(BaseModel):
    id: UUID
    user_id: Optional[UUID] = None
    tenant_id: UUID
    action: str
    resource_type: str
    resource_id: Optional[UUID] = None
    patient_id: Optional[UUID] = None
    timestamp: datetime
    ip_address: Optional[str] = None
    user_agent: Optional[str] = None
    details: Optional[Dict[str, Any]] = None

    model_config = ConfigDict(from_attributes=True)

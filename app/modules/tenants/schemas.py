# app/modules/tenants/schemas.py
from pydantic import BaseModel
from uuid import UUID  # 👈 Importamos UUID

class TenantCreate(BaseModel):
    name: str
    address: str | None = None
    phone: str | None = None

class TenantResponse(BaseModel):
    id: UUID  # 👈 ¡CAMBIADO A UUID! Para que Swagger lo muestre correctamente
    name: str
    address: str | None = None
    phone: str | None = None

    model_config = {
        "from_attributes": True
    }
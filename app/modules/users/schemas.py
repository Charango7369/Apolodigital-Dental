# app/modules/users/schemas.py
from pydantic import BaseModel, EmailStr
from uuid import UUID  # 👈 Usamos UUID para todo

class UserCreate(BaseModel):
    full_name: str
    email: EmailStr
    password: str
    role: str
    tenant_id: UUID  # 👈 Cambiado a UUID


class UserResponse(BaseModel):
    id: UUID  # 👈 El usuario usa UUID
    full_name: str
    email: EmailStr
    role: str
    tenant_id: UUID  # 👈 La clínica ahora también usará UUID

    model_config = {
        "from_attributes": True
    }
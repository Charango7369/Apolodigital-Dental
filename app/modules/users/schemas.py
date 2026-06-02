# app/modules/users/schemas.py
from pydantic import BaseModel, EmailStr
from uuid import UUID  # 👈 Reimportamos UUID para el ID del usuario

class UserCreate(BaseModel):
    full_name: str
    email: EmailStr
    password: str
    role: str
    tenant_id: int  # 👈 Sigue siendo int porque la clínica usó el ID 2


class UserResponse(BaseModel):
    id: UUID  # 👈 ¡CORREGIDO! El usuario genera un UUID (ej: "de305d54...")
    full_name: str
    email: EmailStr
    role: str
    tenant_id: int  # 👈 Sigue siendo int para emparejar con la clínica

    model_config = {
        "from_attributes": True
    }
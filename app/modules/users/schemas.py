# app/modules/users/schemas.py
from pydantic import BaseModel, EmailStr

class UserCreate(BaseModel):
    full_name: str
    email: EmailStr
    password: str
    role: str
    tenant_id: int  # 👈 Agregado para que Swagger te pida el ID de la clínica


class UserResponse(BaseModel):
    id: int  # 👈 ¡CORREGIDO! Cambiado de UUID a int para coincidir con tu base de datos
    full_name: str
    email: EmailStr
    role: str
    tenant_id: int  # 👈 Añadido también aquí para saber a qué clínica pertenece al consultar

    model_config = {
        "from_attributes": True
    }
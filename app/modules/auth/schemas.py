# app/modules/auth/schemas.py
from pydantic import BaseModel, ConfigDict
from uuid import UUID


class Token(BaseModel):
    """Respuesta básica del token JWT."""
    access_token: str
    token_type: str


class TokenData(BaseModel):
    """Datos extraídos del payload del JWT (usado en dependencies.py)."""
    sub: str | None = None  # ID del usuario como string


class UserResponse(BaseModel):
    """Datos del usuario que se envían al frontend tras el login."""
    id: UUID
    full_name: str
    email: str
    roles: str  # JSON stringified: '["ADMIN","DOCTOR"]'
    tenant_id: UUID

    model_config = ConfigDict(from_attributes=True)


class LoginResponse(BaseModel):
    """Respuesta completa del endpoint /auth/login."""
    access_token: str
    token_type: str
    user: UserResponse
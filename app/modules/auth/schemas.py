# app/modules/auth/schemas.py
from typing import Optional
from uuid import UUID
from pydantic import BaseModel, ConfigDict, Field


class Token(BaseModel):
    """Respuesta básica del token JWT."""
    access_token: str
    token_type: str = "bearer"


class TokenData(BaseModel):
    """Datos extraídos del payload del JWT (usado en dependencies.py)."""
    sub: Optional[str] = None
    tenant_id: Optional[str] = None
    roles: Optional[list] = None
    scope: Optional[str] = None
    type: Optional[str] = None
    jti: Optional[str] = None


class UserResponse(BaseModel):
    """Datos del usuario que se envían al frontend tras el login."""
    id: UUID
    full_name: str
    email: str
    roles: str  # JSON stringified: '["ADMIN","DOCTOR"]'
    tenant_id: UUID

    model_config = ConfigDict(from_attributes=True)


class LoginResponse(BaseModel):
    """
    Respuesta del endpoint /auth/login.
    Soporta tanto inicio de sesión directo (Access + Refresh Token)
    como desafío intermedio MFA (mfa_required=True con token mfa_pending).
    """
    access_token: Optional[str] = None
    refresh_token: Optional[str] = None
    token_type: str = "bearer"
    user: Optional[UserResponse] = None
    csrf_token: Optional[str] = None
    mfa_required: bool = False
    mfa_token: Optional[str] = None
    message: Optional[str] = None


class RefreshTokenRequest(BaseModel):
    """Petición de rotación de tokens (RTR). Soporta cuerpo JSON o Cookie HttpOnly."""
    refresh_token: Optional[str] = Field(None, description="Token de refresco. Opcional si se envía en cookie HttpOnly.")


class TokenRefreshResponse(BaseModel):
    """Respuesta tras una rotación exitosa de tokens."""
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    csrf_token: Optional[str] = None
    user: Optional[UserResponse] = None


class LogoutRequest(BaseModel):
    """Petición de revocación de sesión / logout."""
    refresh_token: Optional[str] = None


class MFASetupResponse(BaseModel):
    """Datos de inicialización de MFA TOTP."""
    secret: str
    otpauth_url: str
    instructions: str = "Escanee el código QR o ingrese la clave manual en su app de autenticación (Google Authenticator, Authy, etc.)."


class MFAVerifyRequest(BaseModel):
    """Verificación de código de 6 dígitos para activar MFA."""
    code: str = Field(..., min_length=6, max_length=6, pattern="^[0-9]{6}$", description="Código TOTP de 6 dígitos.")


class MFAChallengeRequest(BaseModel):
    """Desafío de segundo factor de autenticación tras login inicial."""
    mfa_token: str = Field(..., description="Token temporal con scope mfa_pending.")
    code: str = Field(..., min_length=6, max_length=6, pattern="^[0-9]{6}$", description="Código TOTP de 6 dígitos.")


class MFADisableRequest(BaseModel):
    """Petición para deshabilitar MFA requiriendo contraseña y código actual."""
    password: str = Field(..., min_length=1)
    code: str = Field(..., min_length=6, max_length=6, pattern="^[0-9]{6}$")


class GenericStatusResponse(BaseModel):
    """Respuesta genérica de estado de operación."""
    success: bool
    message: str

# app/modules/auth/schemas.py
from pydantic import BaseModel
from typing import Optional

# Estructura del token que viaja al frontend tras un login exitoso
class Token(BaseModel):
    access_token: str
    token_type: str

# Los datos que van encriptados dentro del token (el "subject")
class TokenData(BaseModel):
    user_id: Optional[str] = None
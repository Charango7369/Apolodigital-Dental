from pydantic import BaseModel, EmailStr
from uuid import UUID


class UserCreate(BaseModel):
    full_name: str
    email: EmailStr
    password: str
    role: str


class UserResponse(BaseModel):
    id: UUID
    full_name: str
    email: EmailStr
    role: str

    model_config = {
        "from_attributes": True
    }
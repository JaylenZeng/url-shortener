from datetime import datetime
import uuid

from pydantic import BaseModel, EmailStr, ConfigDict, Field


class RegisterRequest(BaseModel):
  email: EmailStr
  password: str = Field(min_length=8, max_length=72)

class LoginRequest(BaseModel):
  email: EmailStr
  password: str

class UserResponse(BaseModel):
  model_config = ConfigDict(from_attributes=True)
  
  id: uuid.UUID
  email: EmailStr
  created_at: datetime

class TokenResponse(BaseModel):
  access_token: str
  token_type: str = "bearer"
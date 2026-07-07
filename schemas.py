from pydantic import BaseModel, EmailStr
from typing import List, Optional
from datetime import datetime

# --- Token Schemas ---
class Token(BaseModel):
    access_token: str
    token_type: str

class TokenData(BaseModel):
    email: Optional[str] = None

# --- Device Schemas ---
class AntigravityDeviceBase(BaseModel):
    name: str
    core_stability: float
    max_altitude: float

class AntigravityDeviceCreate(AntigravityDeviceBase):
    pass

class AntigravityDeviceResponse(AntigravityDeviceBase):
    id: int
    created_at: datetime
    user_id: int

    class Config:
        from_attributes = True

# --- User Schemas ---
class UserBase(BaseModel):
    email: EmailStr

class UserCreate(UserBase):
    password: str

class UserResponse(UserBase):
    id: int
    created_at: datetime
    
    class Config:
        from_attributes = True

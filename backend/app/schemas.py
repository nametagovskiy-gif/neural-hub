from pydantic import BaseModel, EmailStr, Field

class Credentials(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)

class KeyCreate(BaseModel):
    name: str = Field(default="Default", min_length=1, max_length=80)

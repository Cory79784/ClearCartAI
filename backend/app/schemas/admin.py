from pydantic import BaseModel, Field


class CreateUserRequest(BaseModel):
    username: str = Field(min_length=3, max_length=64)
    password: str = Field(min_length=6, max_length=256)
    role: str = Field(default="user")


class UserResponse(BaseModel):
    username: str
    role: str

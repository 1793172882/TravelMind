"""Request and response schemas for local Web authentication."""

from pydantic import BaseModel, Field


class CredentialsRequest(BaseModel):
    username: str = Field(min_length=3, max_length=50, pattern=r"^[A-Za-z0-9_.-]+$")
    password: str = Field(min_length=8, max_length=128)


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user_id: str
    username: str


class CurrentUserResponse(BaseModel):
    user_id: str
    username: str
    authenticated: bool

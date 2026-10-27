from pydantic import BaseModel, Field


class LoginRequest(BaseModel):
    username: str
    password: str


class TokenOut(BaseModel):
    access_token: str
    token_type: str = "bearer"


class PasswordChangeRequest(BaseModel):
    """修改密码请求体（需 Bearer 鉴权）"""

    old_password: str = Field(min_length=1, description="当前密码")
    new_password: str = Field(min_length=6, description="新密码至少 6 位")


class PasswordChangeOut(BaseModel):
    detail: str

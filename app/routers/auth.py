from fastapi import APIRouter, Depends, HTTPException, status
from sqlmodel.ext.asyncio.session import AsyncSession

from app.auth import create_access_token, get_current_user
from app.dao import UserCrud
from app.database import get_session
from app.model import User
from app.schema import LoginRequest, TokenOut, UserOut

router = APIRouter()


@router.post("/login", response_model=TokenOut)
async def login(data: LoginRequest, session: AsyncSession = Depends(get_session)):
    crud = UserCrud(session)
    user = await crud.get_by_username(data.username)
    if user is None or not user.check_password(data.password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="用户名或密码错误",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return TokenOut(access_token=create_access_token(user.id))


@router.get("/me", response_model=UserOut)
async def me(user: User = Depends(get_current_user)):
    return user

from sqlmodel.ext.asyncio.session import AsyncSession
from app.dao import UserCrud


class UserService:
    def __init__(self, session: AsyncSession) -> None:
        self.crud = UserCrud(session)

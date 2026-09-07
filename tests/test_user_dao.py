import pytest
import pydantic
from sqlmodel.ext.asyncio.session import AsyncSession
from app.model import User
from app.dao import UserCrud


@pytest.fixture
def user_crud(session: AsyncSession):
    return UserCrud(session)


async def _create_user(session: AsyncSession, username="testuser", nickname="测试用户", password="123456") -> User:
    user = User.create_user(username=username, nickname=nickname, password=password)
    session.add(user)
    await session.flush()
    await session.refresh(user)
    return user


async def test_list_all_user_empty(session: AsyncSession, user_crud: UserCrud):
    users = await user_crud.list_all_user()
    assert users == []


async def test_list_all_user(session: AsyncSession, user_crud: UserCrud):
    await _create_user(session, "user1", "用户1")
    await _create_user(session, "user2", "用户2")
    users = await user_crud.list_all_user()
    assert len(users) == 2
    assert users[0].username == "user1"
    assert users[1].username == "user2"


async def test_get_total_count_empty(session: AsyncSession, user_crud: UserCrud):
    count = await user_crud.get_total_count()
    assert count == 0


async def test_get_total_count(session: AsyncSession, user_crud: UserCrud):
    await _create_user(session, "user1", "用户1")
    await _create_user(session, "user2", "用户2")
    count = await user_crud.get_total_count()
    assert count == 2


async def test_get_by_user_id(session: AsyncSession, user_crud: UserCrud):
    user = await _create_user(session)
    result = await user_crud.get_by_user_id(user.id)
    assert result is not None
    assert result.nickname == "测试用户"


async def test_get_by_user_id_not_found(session: AsyncSession, user_crud: UserCrud):
    """DAO 在找不到记录时 model_validate(None) 会抛 ValidationError"""
    with pytest.raises(pydantic.ValidationError):
        await user_crud.get_by_user_id(999)

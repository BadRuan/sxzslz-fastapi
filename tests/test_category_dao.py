import pytest
from sqlmodel.ext.asyncio.session import AsyncSession
from app.model import Category
from app.dao import CategoryCrud


@pytest.fixture
def category_crud(session: AsyncSession):
    return CategoryCrud(session)


def _make_category(id: int, name: str, slug: str, parent_id: int = 0, path: str = "", level: int = 1, sort: int = 0) -> Category:
    if not path:
        path = f"/{id}/"
    return Category(id=id, name=name, slug=slug, parent_id=parent_id, path=path, level=level, sort=sort)


async def test_query_raw_all_empty(session: AsyncSession, category_crud: CategoryCrud):
    result = await category_crud.query_raw_all()
    assert result == []


async def test_query_raw_all(session: AsyncSession, category_crud: CategoryCrud):
    session.add(_make_category(1, "技术", "tech", sort=1))
    session.add(_make_category(2, "生活", "life", sort=2))
    await session.flush()

    result = await category_crud.query_raw_all()
    assert len(result) == 2
    assert result[0].name == "技术"
    assert result[1].name == "生活"


async def test_query_all_returns_tree(session: AsyncSession, category_crud: CategoryCrud):
    session.add(_make_category(1, "技术", "tech", sort=1))
    session.add(_make_category(2, "Python", "python", parent_id=1, path="/1/2/", level=2, sort=1))
    session.add(_make_category(3, "生活", "life", sort=2))
    await session.flush()

    roots = await category_crud.query_all()
    assert len(roots) == 2
    tech = roots[0]
    assert tech.name == "技术"
    assert len(tech.children) == 1
    assert tech.children[0].name == "Python"


async def test_query_by_category_id(session: AsyncSession, category_crud: CategoryCrud):
    session.add(_make_category(1, "技术", "tech"))
    await session.flush()

    result = await category_crud.query_by_category_id(1)
    assert result is not None
    assert result.name == "技术"


async def test_query_by_category_id_not_found(session: AsyncSession, category_crud: CategoryCrud):
    result = await category_crud.query_by_category_id(999)
    assert result is None

import pytest
import pydantic
from sqlmodel.ext.asyncio.session import AsyncSession
from app.model import User, Category, Article, ArticleCategory
from app.dao import ArticleCategoryCrud


@pytest.fixture
def ac_crud(session: AsyncSession):
    return ArticleCategoryCrud(session)


async def _setup_data(session: AsyncSession):
    user = User.create_user(username="author", nickname="作者", password="123456")
    session.add(user)
    await session.flush()

    cat = Category(id=1, name="技术", slug="tech", parent_id=0, path="/1/", level=1)
    session.add(cat)
    await session.flush()

    article = Article(title="测试文章", content="内容", user_id=user.id, status=1, slug="test-art")
    session.add(article)
    await session.flush()

    ac = ArticleCategory(article_id=article.id, category_id=cat.id, is_primary=1)
    session.add(ac)
    await session.flush()

    return article, cat, ac


async def test_query_primary_by_article_id(session: AsyncSession, ac_crud: ArticleCategoryCrud):
    article, cat, ac = await _setup_data(session)
    result = await ac_crud.query_primary_by_article_id(article.id)
    assert result is not None
    assert result.article_id == article.id
    assert result.category_id == cat.id
    assert result.is_primary == 1


async def test_query_primary_by_article_id_not_found(session: AsyncSession, ac_crud: ArticleCategoryCrud):
    """DAO 在找不到记录时 model_validate(None) 会抛 ValidationError"""
    with pytest.raises(pydantic.ValidationError):
        await ac_crud.query_primary_by_article_id(999)


async def test_query_primary_only_returns_primary(session: AsyncSession, ac_crud: ArticleCategoryCrud):
    user = User.create_user(username="a", nickname="b", password="123")
    session.add(user)
    await session.flush()

    cat1 = Category(id=1, name="A", slug="a", parent_id=0, path="/1/", level=1)
    cat2 = Category(id=2, name="B", slug="b", parent_id=0, path="/2/", level=1)
    session.add_all([cat1, cat2])
    await session.flush()

    article = Article(title="t", content="c", user_id=user.id, status=1, slug="s")
    session.add(article)
    await session.flush()

    ac_primary = ArticleCategory(article_id=article.id, category_id=cat1.id, is_primary=1)
    ac_secondary = ArticleCategory(article_id=article.id, category_id=cat2.id, is_primary=0)
    session.add_all([ac_primary, ac_secondary])
    await session.flush()

    result = await ac_crud.query_primary_by_article_id(article.id)
    assert result is not None
    assert result.category_id == cat1.id
    assert result.is_primary == 1

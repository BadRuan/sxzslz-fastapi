import pytest
from sqlmodel.ext.asyncio.session import AsyncSession
from app.model import User, Category, Article, ArticleCategory
from app.dao import ArticleCrud


@pytest.fixture
def article_crud(session: AsyncSession):
    return ArticleCrud(session)


async def _setup_base_data(session: AsyncSession):
    """创建测试所需的基础数据：用户、分类、文章、文章分类关联"""
    user = User.create_user(username="author", nickname="作者", password="123456")
    session.add(user)
    await session.flush()

    cat1 = Category(id=1, name="技术", slug="tech", parent_id=0, path="/1/", level=1, sort=1)
    cat2 = Category(id=2, name="Python", slug="python", parent_id=1, path="/1/2/", level=2, sort=1)
    session.add_all([cat1, cat2])
    await session.flush()

    article1 = Article(title="文章1", content="内容1", user_id=user.id, status=1, slug="art1", cover_img_slug="cover1")
    article2 = Article(title="文章2", content="内容2", user_id=user.id, status=1, slug="art2", cover_img_slug="cover2")
    article3 = Article(title="草稿", content="草稿内容", user_id=user.id, status=0, slug="draft1", cover_img_slug="cover3")
    session.add_all([article1, article2, article3])
    await session.flush()

    ac1 = ArticleCategory(article_id=article1.id, category_id=cat1.id, is_primary=1)
    ac2 = ArticleCategory(article_id=article2.id, category_id=cat2.id, is_primary=1)
    ac3 = ArticleCategory(article_id=article3.id, category_id=cat1.id, is_primary=1)
    session.add_all([ac1, ac2, ac3])
    await session.flush()

    return user, cat1, cat2, article1, article2, article3


async def test_count_category_article(session: AsyncSession, article_crud: ArticleCrud):
    await _setup_base_data(session)
    # cat1 路径 /1/，cat2 路径 /1/2/，cat2 以 cat1 路径开头
    # 所以查 cat1 应该包含 cat1 和 cat2 下的已发布文章
    count = await article_crud.count_category_article(1)
    assert count == 2  # article1(cat1) + article2(cat2)


async def test_count_category_article_leaf(session: AsyncSession, article_crud: ArticleCrud):
    await _setup_base_data(session)
    count = await article_crud.count_category_article(2)
    assert count == 1  # article2(cat2)


async def test_query_category_article(session: AsyncSession, article_crud: ArticleCrud):
    await _setup_base_data(session)
    articles = await article_crud.query_category_article(1, skip=0, limit=10)
    assert len(articles) == 2


async def test_query_category_article_pagination(session: AsyncSession, article_crud: ArticleCrud):
    await _setup_base_data(session)
    articles = await article_crud.query_category_article(1, skip=0, limit=1)
    assert len(articles) == 1


async def test_query_recommended_article(session: AsyncSession, article_crud: ArticleCrud):
    await _setup_base_data(session)
    articles = await article_crud.query_recommended_article(limit=10)
    assert len(articles) == 2  # 只返回已发布的


async def test_increase_view_count(session: AsyncSession, article_crud: ArticleCrud):
    user, _, _, article1, _, _ = await _setup_base_data(session)
    await article_crud.increase_view_count("art1")
    await session.flush()

    await session.refresh(article1)
    assert article1.view_count == 1


async def test_query_detail_by_slug(session: AsyncSession, article_crud: ArticleCrud):
    await _setup_base_data(session)
    detail = await article_crud.query_detail_by_slug("art1")
    assert detail is not None
    assert detail.title == "文章1"


async def test_query_detail_by_slug_not_found(session: AsyncSession, article_crud: ArticleCrud):
    """DAO 在找不到记录时 model_validate(None) 会抛 ValidationError"""
    import pydantic
    await _setup_base_data(session)
    with pytest.raises(pydantic.ValidationError):
        await article_crud.query_detail_by_slug("nonexistent")

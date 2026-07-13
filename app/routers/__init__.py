from .user import router as user_router
from .category import router as category_router
from .article import router as article_router

__all__ = [
    'user_router',
    'category_router',
    'article_router'
]
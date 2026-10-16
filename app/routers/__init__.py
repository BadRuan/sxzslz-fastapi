from .base import router as baseinfo_router
from .category import router as category_router
from .image import router as image_router
from .document import router as document_router
from .article import router as article_router

__all__ = [
    'baseinfo_router',
    'category_router',
    'image_router',
    'document_router',
    'article_router'
]
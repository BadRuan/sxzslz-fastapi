from .baseInfo import router as baseinfo_router
from .article import router as article_router
from .image import router as image_router
from .document import router as document_router

__all__ = [
    'baseinfo_router',
    'article_router',
    'image_router',
    'document_router'
]
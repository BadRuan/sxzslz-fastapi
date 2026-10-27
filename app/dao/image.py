from app.dao.file import FileCrud
from app.model import Image


class ImageCrud(FileCrud[Image]):
    """image 表：分页按 id 倒序（最新在前）"""

    model = Image
    order_by_field = "id"

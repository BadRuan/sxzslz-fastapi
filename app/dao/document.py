from app.dao.file import FileCrud
from app.model import Document


class DocumentCrud(FileCrud[Document]):
    """document 表：分页按上传时间倒序（最新在前）"""

    model = Document
    order_by_field = "uploaded_at"

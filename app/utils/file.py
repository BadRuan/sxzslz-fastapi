from uuid import uuid4


def generate_unique_filename(filename: str) -> str:
    """根据原始文件名生成唯一的文件名"""
    ext = filename.rsplit('.', 1)[1].lower()
    return f"{uuid4().hex}.{ext}"

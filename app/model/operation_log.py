"""操作日志模型（审计日志）。

记录账户/文章/图片/文档等关键操作，字段：操作类型、操作对象类型与标识/名称、
操作时间、操作者（id/昵称）、操作结果、失败原因、客户端 IP 与 User-Agent。

新增模型须在 app/model/__init__.py 中导出，才会被 SQLModel.metadata.create_all 建表。
"""

from datetime import datetime
from typing import Optional
from uuid import uuid4

from sqlmodel import Field, SQLModel


class OperationLog(SQLModel, table=True):
    __tablename__: str = "operation_log"

    id: int = Field(primary_key=True, default=None)  # type: ignore[arg-type]
    # 操作类型，如 create_account / update_account / delete_account /
    #    create_article / update_article / delete_article /
    #    upload_image / update_image_name / delete_image /
    #    upload_document / update_document_name / delete_document
    action: str = Field(index=True)
    # 操作对象类型：account / article / image / document
    object_type: str = Field(index=True)
    # 操作对象的唯一标识（文章/图片/文档的 slug，账户的用户 id）
    object_id: str = Field(index=True)
    # 操作对象名称（标题、文件名、用户名/昵称），便于审计可读
    object_name: Optional[str] = Field(default=None)
    # 操作者用户 id；系统内部/无登录态操作时为空
    operator_id: Optional[int] = Field(default=None, index=True)
    # 操作者昵称，冗余保存以便直接查看无需关联用户表
    operator_name: Optional[str] = Field(default=None)
    # 操作时间（服务器本地时间）
    created_at: datetime = Field(default_factory=datetime.now, index=True)
    # 操作结果：success / failed
    result: str = Field(index=True)
    # 失败原因（result=failed 时填写）
    message: Optional[str] = Field(default=None)
    # 客户端 IP（来自请求头 X-Forwarded-For 或直接连接 IP）
    client_ip: Optional[str] = Field(default=None)
    # 客户端 User-Agent
    user_agent: Optional[str] = Field(default=None)


def generate_log_id() -> str:
    """兼容占位：日志主键用数据库自增 id，此函数暂不使用，保留以备将来改用 slug。"""
    return uuid4().hex

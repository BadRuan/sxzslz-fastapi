from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, field_serializer


class OperationLogOut(BaseModel):
    """操作日志行（GET /logs/ 返回；超管查全量，普通用户只看本人）。"""

    model_config = ConfigDict(from_attributes=True)

    id: int
    action: str
    object_type: str
    object_id: str
    object_name: Optional[str] = None
    operator_id: Optional[int] = None
    operator_name: Optional[str] = None
    created_at: datetime
    result: str
    message: Optional[str] = None
    client_ip: Optional[str] = None
    user_agent: Optional[str] = None

    @field_serializer("created_at")
    def serialize_created_at(self, value: datetime) -> str:
        """序列化为含时分秒的展示格式（YYYY-MM-DD HH:MM:SS）。"""
        return value.strftime("%Y-%m-%d %H:%M:%S")

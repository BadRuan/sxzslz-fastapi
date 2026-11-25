from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict


class OperationLogOut(BaseModel):
    """操作日志行（GET /logs/ 返回，仅超管可见）。"""

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

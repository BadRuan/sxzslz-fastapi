from uuid import uuid4
from sqlmodel import SQLModel, Field
from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError, InvalidHash

ph = PasswordHasher(
    time_cost=3,       # 迭代次数
    memory_cost=65536, # 内存成本 (64 MB)
    parallelism=4      # 并行线程数
)

def generate_slug() -> str:
    """生成唯一的 slug"""
    return uuid4().hex[:12]


class User(SQLModel, table=True):
    __tablename__: str = "user"

    id: int = Field(primary_key=True, default=None)  # type: ignore[arg-type]
    slug: str = Field(unique=True, default_factory=generate_slug)
    # 用户名
    username: str = Field(unique=True, nullable=False)
    # 昵称
    nickname: str = Field(unique=True, nullable=False)
    # 密码
    password: str = Field(nullable=False)
    
    @classmethod
    def create_user(cls, username: str, nickname: str, password: str):
        hash = ph.hash(password)
        return cls(username=username, nickname=nickname, password=hash)

    def check_password(self, plain_password: str) -> bool:
        try:
            ph.verify(self.password, plain_password)
            return True
        except (VerifyMismatchError, InvalidHash):
            return False

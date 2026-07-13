from typing import Dict
from sqlmodel import SQLModel, Field


class Category(SQLModel, table=True):
    __tablename__: str = "categories"

    id: str = Field(primary_key=True, default=None)  # type: ignore[arg-type]
    name: str = Field(unique=True, nullable=False)

    def __repr__(self) -> str:
        return f"<Category {self.name}>"

    def to_dict(self) -> Dict:
        return {
            "id": self.id,
            "name": self.name
        }

from typing import List, NamedTuple
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    DATABASE_URL: str = "postgresql+asyncpg://user:pass@localhost:5432/dbname"
    DB_ECHO: bool = False
    DEBUG: bool = False
    SECRET_KEY: str = "your-secret-key-change-in-production"
    DEFAULT_USER_ID: int = 1
    # 逗号分隔的允许来源，如 "http://localhost:3000,https://example.com"
    CORS_ORIGINS: str = "*"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 12

    model_config = SettingsConfigDict(
        env_file = ".env",
        env_file_encoding= 'utf-8',
        extra = "ignore"
    )

settings: Settings = Settings()

def cors_origins() -> List[str]:
    return [o.strip() for o in settings.CORS_ORIGINS.split(",") if o.strip()]

class IMAGE_DIR(NamedTuple):
    image_raw: str
    image_preview: str
    document: str

class ALLOW_TYPE(NamedTuple):
    image: List[str]
    document: List[str]

base_dir = './uploads/'

upload_dir = IMAGE_DIR(
    image_raw= base_dir + 'image/raw', 
    image_preview= base_dir + 'image/preview',
    document= base_dir + 'document'
)

allow_type: ALLOW_TYPE = ALLOW_TYPE(
    image = ["image/jpeg", "image/png", "image/webp"],
    document=[
        "application/msword",
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        "application/vnd.ms-excel",
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        "application/vnd.ms-powerpoint",
        "application/vnd.openxmlformats-officedocument.presentationml.presentation",
        "text/plain",
        "application/pdf",
        "application/zip"
    ]
)

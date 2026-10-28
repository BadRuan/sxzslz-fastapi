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
    # 上传大小上限（MB）：图片 / 文档，超出返回 400
    MAX_IMAGE_SIZE_MB: int = 10
    MAX_DOCUMENT_SIZE_MB: int = 50

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


settings: Settings = Settings()


def cors_origins() -> List[str]:
    return [o.strip() for o in settings.CORS_ORIGINS.split(",") if o.strip()]


class UploadDir(NamedTuple):
    """上传文件落盘目录（相对项目根）。"""

    image_raw: str
    image_preview: str
    document: str


class AllowType(NamedTuple):
    """上传文件允许的 MIME 类型白名单（按扩展名/Content-Type 对齐常见格式）。"""

    image: List[str]
    document: List[str]


base_dir = "./uploads/"

upload_dir = UploadDir(
    image_raw=base_dir + "image/raw",
    image_preview=base_dir + "image/preview",
    document=base_dir + "document",
)

# 图片：仅列 PIL 可解码生成 WebP 预览的格式（SVG/HEIC/AVIF 等无插件会预览失败，不放开）
allow_type: AllowType = AllowType(
    image=[
        "image/jpeg",  # .jpg / .jpeg
        "image/png",  # .png
        "image/gif",  # .gif
        "image/webp",  # .webp
        "image/bmp",  # .bmp
        "image/x-ms-bmp",  # Windows 资源管理器里的 .bmp 常报这个
        "image/tiff",  # .tif / .tiff
        "image/x-icon",  # .ico
        "image/vnd.microsoft.icon",  # .ico 变体
    ],
    document=[
        # 纯文本 / 数据
        "text/plain",  # .txt
        "text/csv",  # .csv
        "application/csv",
        "text/markdown",  # .md
        "text/rtf",
        "application/rtf",  # .rtf
        # PDF
        "application/pdf",  # .pdf
        # Microsoft Office（旧版 + OOXML + 启用宏的常见 MIME）
        "application/msword",  # .doc
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document",  # .docx
        "application/vnd.ms-word.document.macroEnabled.12",  # .docm
        "application/vnd.ms-excel",  # .xls
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",  # .xlsx
        "application/vnd.ms-excel.sheet.macroEnabled.12",  # .xlsm
        "application/vnd.ms-powerpoint",  # .ppt
        "application/vnd.openxmlformats-officedocument.presentationml.presentation",  # .pptx
        "application/vnd.ms-powerpoint.presentation.macroEnabled.12",  # .pptm
        # OpenDocument
        "application/vnd.oasis.opendocument.text",  # .odt
        "application/vnd.oasis.opendocument.spreadsheet",  # .ods
        "application/vnd.oasis.opendocument.presentation",  # .odp
        # 压缩包
        "application/zip",  # .zip
        "application/x-zip-compressed",  # Windows 资源管理器 .zip
        "application/x-7z-compressed",  # .7z
        "application/x-rar-compressed",  # .rar（旧 MIME）
        "application/vnd.rar",  # .rar（IANA 注册 MIME）
        "application/gzip",  # .gz / .tgz
        "application/x-gzip",
        "application/x-tar",  # .tar
        # 电子书
        "application/epub+zip",  # .epub
    ],
)

# 展示给前端的友好后缀列表（与 allow_type 同步维护；报错文案引用）
IMAGE_TYPE_LABEL = "JPG、PNG、GIF、WebP、BMP、TIFF、ICO"
DOCUMENT_TYPE_LABEL = (
    "txt、csv、md、rtf、pdf、"
    "doc、docx、docm、xls、xlsx、xlsm、ppt、pptx、pptm、"
    "odt、ods、odp、zip、7z、rar、gz、tar、epub"
)

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    DATABASE_URL: str = "postgresql+asyncpg://user:pass@localhost:5432/dbname"
    DB_ECHO: bool = False
    DEBUG: bool = False
    SECRET_KEY: str = "your-secret-key-change-in-production"
    

    model_config = SettingsConfigDict(
        env_file = ".env",
        env_file_encoding= 'utf-8',
        extra = "ignore"
        )

settings: Settings = Settings()
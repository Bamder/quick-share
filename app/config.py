import os
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    APP_NAME: str = "文件闪传系统"
    APP_VERSION: str = "1.0.0"
    DEBUG: bool = True
    DATABASE_URL: str = "mysql+pymysql://root:hyhy1202@localhost:3306/quick_share_datagrip?charset=utf8mb4"
    API_V1_PREFIX: str = "/api/v1"
    ALLOWED_ORIGINS: list = ["*"]
    
    class Config:
        env_file = ".env"

settings = Settings()

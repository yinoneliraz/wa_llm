from pydantic_settings import BaseSettings
from typing import Optional

class Settings(BaseSettings):
    # API settings
    PORT: int = 5001
    HOST: str = "0.0.0.0"
    
    # Database settings
    DB_HOST: str = "localhost"
    DB_PORT: int = 5432
    DB_NAME: str = "postgres"
    DB_USER: str = "postgres"
    DB_PASSWORD: str

    # WhatsApp settings
    MY_NUMBER: str
    WHATSAPP_HOST: str
    WHATSAPP_BASIC_AUTH_PASSWORD: Optional[str] = None
    WHATSAPP_BASIC_AUTH_USER: Optional[str] = None

    ANTHROPIC_API_KEY: str
    
    # Optional settings
    DEBUG: bool = False
    LOG_LEVEL: str = "INFO"

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
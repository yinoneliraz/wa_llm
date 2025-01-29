from typing import Optional

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    # API settings
    port: int = 5001
    host: str = "0.0.0.0"

    # Database settings
    db_uri: str

    # WhatsApp settings
    my_number: str
    whatsapp_host: str
    whatsapp_basic_auth_password: Optional[str] = None
    whatsapp_basic_auth_user: Optional[str] = None

    anthropic_api_key: str

    # Optional settings
    debug: bool = False
    log_level: str = "INFO"

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        arbitrary_types_allowed=True,
        case_sensitive=False,
        extra="ignore",
    )

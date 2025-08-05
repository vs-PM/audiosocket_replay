"""
Конфигурация микросервиса. Использует pydantic для загрузки переменных окружения.
"""

from pydantic import BaseSettings, Field
from typing import Literal
from dotenv import load_dotenv

load_dotenv()  # Загрузить переменные из .env файла

class Settings(BaseSettings):
    """
    Конфигурация приложения. Все значения берутся из ENV или .env файла.
    """
    AUDIO_PORT: int = Field(default=4000, description="TCP порт для AudioSocket-сервера")
    WS_PORT: int = Field(default=4001, description="Порт для WebSocket-сервера")
    LOG_LEVEL: str = Field(default="INFO", description="Уровень логирования")
    PROD: Literal['true', 'false', 'True', 'False', True, False] = Field(
        default='false', description="True если PROD, иначе False"
    )

    class Config:
        env_file = ".env"
        case_sensitive = False
        extra = "ignore"         # <<< вот эта строчка решает вашу задачу!

settings = Settings()
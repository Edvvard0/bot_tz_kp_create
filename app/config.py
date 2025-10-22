import os
from typing import List
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    BOT_TOKEN: str
    ADMIN_IDS: List[int]

    DB_URL: str

    CHAT_GPT_API_KEY: str
    CHAT_GPT_MODEL: str

    BUSINESS_PARTNER_ID: int
    TEAM_PARTNER_ID: int

    REMINDER_DELAY_SECONDS_NEW: int = 7200

    model_config = SettingsConfigDict(
        env_file=os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", ".env")
    )

    def get_webhook_url(self) -> str:
        """Возвращает URL вебхука с кодированием специальных символов."""
        return f"{self.BASE_SITE}/webhook"


# Получаем параметры для загрузки переменных среды
settings = Settings()
database_url = settings.DB_URL
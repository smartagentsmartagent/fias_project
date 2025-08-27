"""
Конфигурация для FIAS адресного поиска
"""
import os
from typing import Optional
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Настройки приложения"""
    
    # Elasticsearch
    ES_URL: str = "http://147.45.214.115:9200"
    ES_API_KEY: Optional[str] = None
    ES_USER: Optional[str] = None
    ES_PASS: Optional[str] = None
    ES_INDEX: str = "fias_addresses_v2"
    ES_TIMEOUT: int = 60
    
    # MySQL FIAS
    MYSQL_HOST: str = "mysql.node7.smartagent.ru"
    MYSQL_PORT: int = 3306
    MYSQL_USER: str = "rzimin"
    MYSQL_PASSWORD: str = "NVij4JJPkQt"
    MYSQL_DATABASE: str = "smartagent"
    
    # API
    API_HOST: str = "0.0.0.0"
    API_PORT: int = 8000
    API_DEBUG: bool = True
    
    # Поиск
    SEARCH_LIMIT: int = 10
    MAX_SEARCH_LIMIT: int = 100
    
    # Логирование
    LOG_LEVEL: str = "INFO"
    
    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


# Глобальный экземпляр настроек
settings = Settings()


def get_elasticsearch_config():
    """Конфигурация для подключения к Elasticsearch"""
    config = {
        "hosts": [settings.ES_URL],
        "timeout": settings.ES_TIMEOUT
    }
    
    # API Key аутентификация (приоритет)
    if settings.ES_API_KEY:
        config["api_key"] = settings.ES_API_KEY
    # Basic Auth (альтернатива)
    elif settings.ES_USER and settings.ES_PASS:
        config["http_auth"] = (settings.ES_USER, settings.ES_PASS)
    
    return config


def get_mysql_url() -> str:
    """URL для подключения к MySQL"""
    return (
        f"mysql+mysqlconnector://{settings.MYSQL_USER}:{settings.MYSQL_PASSWORD}"
        f"@{settings.MYSQL_HOST}:{settings.MYSQL_PORT}/{settings.MYSQL_DATABASE}"
    )

"""
Конфигурация для FIAS адресного поиска
"""
import os
from typing import Optional
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Настройки приложения"""
    
    # Elasticsearch
    ES_HOST: str = "localhost"
    ES_PORT: int = 9200
    ES_INDEX: str = "fias_addresses"
    ES_TIMEOUT: int = 60  # Увеличиваем таймаут для массовых запросов
    
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


def get_elasticsearch_url() -> str:
    """URL для подключения к Elasticsearch"""
    return f"http://{settings.ES_HOST}:{settings.ES_PORT}"


def get_mysql_url() -> str:
    """URL для подключения к MySQL"""
    return (
        f"mysql+mysqlconnector://{settings.MYSQL_USER}:{settings.MYSQL_PASSWORD}"
        f"@{settings.MYSQL_HOST}:{settings.MYSQL_PORT}/{settings.MYSQL_DATABASE}"
    )

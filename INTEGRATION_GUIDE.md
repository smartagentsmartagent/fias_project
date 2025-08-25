# Инструкция по интеграции с Elasticsearch для Background Agent

## Текущее состояние сервера

### Установка Elasticsearch
- **Тип установки**: Standalone сервис (systemd)
- **Версия**: Elasticsearch 8.11.0
- **Сервис**: `elasticsearch-standalone.service`
- **Путь установки**: `/opt/elasticsearch-8.11.0/`
- **Статус**: Активен и работает

### Сетевая конфигурация
- **Публичный IP**: `147.45.214.115`
- **Локальные IP**: `147.45.214.115`, `172.18.0.1`, `172.17.0.1`
- **Порт**: `9200` (HTTP)
- **Привязка**: `0.0.0.0:9200` (доступен извне)

### Безопасность
- **X-Pack Security**: Отключен (`xpack.security.enabled: false`)
- **TLS/SSL**: Не используется
- **Аутентификация**: Не требуется
- **Индексы**: `fias_addresses_v2` (3,272,152 документа)

### Файрвол
- **UFW**: Неактивен
- **iptables**: Нет правил для порта 9200
- **Доступ**: Порт 9200 открыт для всех подключений

## Рекомендуемая конфигурация безопасности

### Вариант A: API Key (рекомендуется)

#### 1. Включение X-Pack Security
```bash
# Остановить Elasticsearch
sudo systemctl stop elasticsearch-standalone

# Редактировать конфигурацию
sudo nano /opt/elasticsearch-8.11.0/config/elasticsearch.yml
```

Добавить/изменить:
```yaml
xpack.security.enabled: true
xpack.security.http.ssl.enabled: true
xpack.security.http.ssl.key: /path/to/elasticsearch.key
xpack.security.http.ssl.certificate: /path/to/elasticsearch.crt
```

#### 2. Создание API Key
```bash
# Создать API Key для Background Agent
curl -X POST "http://localhost:9200/_security/api_key" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "cursor-agent",
    "role_descriptors": {
      "searcher": {
        "cluster": ["monitor"],
        "index": [
          {
            "names": ["fias*", "addresses*"],
            "privileges": ["read", "view_index_metadata"]
          }
        ]
      }
    }
  }'
```

#### 3. Проверка API Key
```bash
# Проверить подключение с API Key
curl -H "Authorization: ApiKey YOUR_API_KEY_HERE" \
  "http://localhost:9200/_cat/indices"
```

### Вариант B: Basic Authentication

#### 1. Создание роли и пользователя
```bash
# Создать роль для поиска
curl -X POST "http://localhost:9200/_security/role/cursor_searcher" \
  -H "Content-Type: application/json" \
  -d '{
    "cluster": ["monitor"],
    "indices": [
      {
        "names": ["fias*", "addresses*"],
        "privileges": ["read", "view_index_metadata"]
      }
    ]
  }'

# Создать пользователя
curl -X POST "http://localhost:9200/_security/user/cursor_agent" \
  -H "Content-Type: application/json" \
  -d '{
    "password": "YOUR_SECURE_PASSWORD",
    "roles": ["cursor_searcher"],
    "full_name": "Cursor Background Agent"
  }'
```

#### 2. Проверка Basic Auth
```bash
# Проверить подключение с Basic Auth
curl -u cursor_agent:YOUR_SECURE_PASSWORD \
  "http://localhost:9200/_cat/indices"
```

## Конфигурация для Background Agent

### 1. Файл .cursor/environment.json
```json
{
  "install": "pip install -r requirements.txt",
  "env": {
    "ES_URL": "${{ES_URL}}",
    "ES_API_KEY": "${{ES_API_KEY}}"
  },
  "terminals": [
    {
      "name": "API",
      "command": "python -m uvicorn api.main:app --host 0.0.0.0 --port 8000 --reload"
    }
  ]
}
```

### 2. Файл .env.example
```bash
# Elasticsearch Configuration
ES_URL=http://147.45.214.115:9200
ES_API_KEY=your_api_key_here

# Alternative Basic Auth (if not using API Key)
ES_USER=cursor_agent
ES_PASS=your_password_here

# Application Settings
API_HOST=0.0.0.0
API_PORT=8000
LOG_LEVEL=INFO
```

### 3. Обновленная конфигурация settings.py
```python
"""
Конфигурация для FIAS адресного поиска
"""
import os
from typing import Optional
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Настройки приложения"""
    
    # Elasticsearch
    ES_URL: str = "http://localhost:9200"
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
```

## Настройка Cursor Secrets

### В Cursor IDE:
1. Откройте **Settings** → **Secrets**
2. Добавьте следующие секреты:
   - `ES_URL`: `http://147.45.214.115:9200`
   - `ES_API_KEY`: `ваш_api_key_здесь` (если используете API Key)
   - `ES_USER`: `cursor_agent` (если используете Basic Auth)
   - `ES_PASS`: `ваш_пароль_здесь` (если используете Basic Auth)

## Рекомендации по безопасности

### 1. Файрвол (рекомендуется)
```bash
# Установить и настроить UFW
sudo apt install ufw
sudo ufw enable

# Разрешить SSH
sudo ufw allow ssh

# Разрешить доступ к Elasticsearch только с IP Cursor
sudo ufw allow from CURSOR_IP to any port 9200

# Или разрешить только локальный доступ и использовать Nginx прокси
sudo ufw allow from 127.0.0.1 to any port 9200
```

### 2. Nginx прокси с HTTPS (альтернатива)
```nginx
# /etc/nginx/sites-available/elasticsearch
server {
    listen 443 ssl;
    server_name your-domain.com;
    
    ssl_certificate /path/to/cert.pem;
    ssl_certificate_key /path/to/key.pem;
    
    location / {
        proxy_pass http://127.0.0.1:9200;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```

## Troubleshooting

### Частые ошибки и решения

#### 1. Ошибка 401 Unauthorized
```bash
# Проверить аутентификацию
curl -v http://localhost:9200/_security/_authenticate

# Проверить API Key
curl -H "Authorization: ApiKey YOUR_KEY" http://localhost:9200/_cat/indices
```

#### 2. Ошибка SSL/TLS
```bash
# Проверить сертификат
openssl s_client -connect localhost:9200 -servername localhost

# Временно отключить проверку SSL (только для тестирования)
curl -k https://localhost:9200
```

#### 3. Ошибка подключения (Connection refused)
```bash
# Проверить статус сервиса
sudo systemctl status elasticsearch-standalone

# Проверить порты
ss -tulpen | grep 9200

# Проверить файрвол
sudo ufw status
sudo iptables -L -n | grep 9200
```

#### 4. CORS ошибки
```bash
# Добавить в elasticsearch.yml
http.cors.enabled: true
http.cors.allow-origin: "*"
http.cors.allow-methods: OPTIONS, HEAD, GET, POST, PUT, DELETE
http.cors.allow-headers: "X-Requested-With,X-Auth-Token,Content-Type,Content-Length,Authorization"
```

#### 5. Ошибки прав доступа
```bash
# Проверить роли пользователя
curl -u username:password http://localhost:9200/_security/user/username

# Проверить права на индексы
curl -u username:password http://localhost:9200/_security/user/_has_privileges \
  -H "Content-Type: application/json" \
  -d '{
    "cluster": ["monitor"],
    "index": [
      {
        "names": ["fias*"],
        "privileges": ["read"]
      }
    ]
  }'
```

## Проверка работоспособности

### Тест подключения
```bash
# Без аутентификации (текущее состояние)
curl http://147.45.214.115:9200

# С API Key
curl -H "Authorization: ApiKey YOUR_API_KEY" http://147.45.214.115:9200

# С Basic Auth
curl -u username:password http://147.45.214.115:9200
```

### Тест поиска
```bash
# Поиск адресов
curl -X GET "http://147.45.214.115:9200/fias_addresses_v2/_search" \
  -H "Content-Type: application/json" \
  -d '{
    "query": {
      "match": {
        "full_address": "Москва"
      }
    },
    "size": 5
  }'
```

## Заключение

Текущая конфигурация Elasticsearch **НЕ БЕЗОПАСНА** для продакшена:
- X-Pack Security отключен
- Порт 9200 открыт для всех
- Нет аутентификации

**Рекомендуемые действия:**
1. Включить X-Pack Security
2. Настроить API Key для Background Agent
3. Ограничить доступ к порту 9200 через файрвол
4. Рассмотреть использование Nginx прокси с HTTPS

После настройки безопасности обновите `ES_URL` в Cursor Secrets на `https://your-domain.com` или ограничьте доступ по IP.




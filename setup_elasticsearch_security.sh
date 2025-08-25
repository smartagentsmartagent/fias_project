#!/bin/bash

# Скрипт для настройки безопасности Elasticsearch
# ВНИМАНИЕ: Выполняйте команды по одной и проверяйте результат!

echo "=== Настройка безопасности Elasticsearch ==="
echo "ВНИМАНИЕ: Этот скрипт содержит команды для настройки безопасности."
echo "Выполняйте команды по одной и проверяйте результат!"
echo ""

# 1. Проверка текущего состояния
echo "1. Проверка текущего состояния:"
echo "   curl -s http://localhost:9200/_cat/indices"
echo ""

# 2. Остановка Elasticsearch
echo "2. Остановка Elasticsearch:"
echo "   sudo systemctl stop elasticsearch-standalone"
echo ""

# 3. Редактирование конфигурации
echo "3. Редактирование конфигурации:"
echo "   sudo nano /opt/elasticsearch-8.11.0/config/elasticsearch.yml"
echo ""
echo "   Добавить/изменить:"
echo "   xpack.security.enabled: true"
echo "   xpack.security.http.ssl.enabled: true"
echo "   xpack.security.http.ssl.key: /path/to/elasticsearch.key"
echo "   xpack.security.http.ssl.certificate: /path/to/elasticsearch.crt"
echo ""

# 4. Запуск Elasticsearch
echo "4. Запуск Elasticsearch:"
echo "   sudo systemctl start elasticsearch-standalone"
echo "   sudo systemctl status elasticsearch-standalone"
echo ""

# 5. Создание API Key
echo "5. Создание API Key для Background Agent:"
echo "   curl -X POST \"http://localhost:9200/_security/api_key\" \\"
echo "     -H \"Content-Type: application/json\" \\"
echo "     -d '{"
echo "       \"name\": \"cursor-agent\","
echo "       \"role_descriptors\": {"
echo "         \"searcher\": {"
echo "           \"cluster\": [\"monitor\"],"
echo "           \"index\": ["
echo "             {"
echo "               \"names\": [\"fias*\", \"addresses*\"],"
echo "               \"privileges\": [\"read\", \"view_index_metadata\"]"
echo "             }"
echo "           ]"
echo "         }"
echo "       }"
echo "     }'"
echo ""

# 6. Альтернатива: создание роли и пользователя
echo "6. Альтернатива: создание роли и пользователя:"
echo "   # Создать роль:"
echo "   curl -X POST \"http://localhost:9200/_security/role/cursor_searcher\" \\"
echo "     -H \"Content-Type: application/json\" \\"
echo "     -d '{"
echo "       \"cluster\": [\"monitor\"],"
echo "       \"indices\": ["
echo "         {"
echo "           \"names\": [\"fias*\", \"addresses*\"],"
echo "           \"privileges\": [\"read\", \"view_index_metadata\"]"
echo "         }"
echo "       ]"
echo "     }'"
echo ""
echo "   # Создать пользователя:"
echo "   curl -X POST \"http://localhost:9200/_security/user/cursor_agent\" \\"
echo "     -H \"Content-Type: application/json\" \\"
echo "     -d '{"
echo "       \"password\": \"YOUR_SECURE_PASSWORD\","
echo "       \"roles\": [\"cursor_searcher\"],"
echo "       \"full_name\": \"Cursor Background Agent\""
echo "     }'"
echo ""

# 7. Настройка файрвола
echo "7. Настройка файрвола:"
echo "   # Установить UFW:"
echo "   sudo apt install ufw"
echo "   sudo ufw enable"
echo ""
echo "   # Разрешить SSH:"
echo "   sudo ufw allow ssh"
echo ""
echo "   # Разрешить доступ к Elasticsearch только с IP Cursor:"
echo "   sudo ufw allow from CURSOR_IP to any port 9200"
echo ""
echo "   # Или разрешить только локальный доступ:"
echo "   sudo ufw allow from 127.0.0.1 to any port 9200"
echo ""

# 8. Проверка
echo "8. Проверка настроек:"
echo "   # Проверить статус файрвола:"
echo "   sudo ufw status"
echo ""
echo "   # Проверить подключение с API Key:"
echo "   curl -H \"Authorization: ApiKey YOUR_API_KEY\" \\"
echo "     \"http://localhost:9200/_cat/indices\""
echo ""
echo "   # Проверить подключение с Basic Auth:"
echo "   curl -u cursor_agent:YOUR_PASSWORD \\"
echo "     \"http://localhost:9200/_cat/indices\""
echo ""

echo "=== Настройка завершена ==="
echo ""
echo "ВАЖНО:"
echo "- Не забудьте сохранить API Key или пароль в безопасном месте"
echo "- Обновите переменные окружения в Cursor Secrets"
echo "- Протестируйте подключение перед использованием в продакшене"




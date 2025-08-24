#!/bin/bash

# Скрипт для тестирования подключения к Elasticsearch
# Использование: ./test_elasticsearch_connection.sh [API_KEY] [USERNAME] [PASSWORD]

ES_URL="http://147.45.214.115:9200"
API_KEY="${1:-}"
USERNAME="${2:-}"
PASSWORD="${3:-}"

echo "=== Тестирование подключения к Elasticsearch ==="
echo "URL: $ES_URL"
echo ""

# 1. Тест без аутентификации (текущее состояние)
echo "1. Тест без аутентификации:"
curl -s "$ES_URL" | jq '.version.number' 2>/dev/null || curl -s "$ES_URL" | head -n 3
echo ""
echo ""

# 2. Тест с API Key (если предоставлен)
if [ -n "$API_KEY" ]; then
    echo "2. Тест с API Key:"
    curl -s -H "Authorization: ApiKey $API_KEY" "$ES_URL/_cat/indices" | head -n 5
    echo ""
    echo ""
fi

# 3. Тест с Basic Auth (если предоставлены учетные данные)
if [ -n "$USERNAME" ] && [ -n "$PASSWORD" ]; then
    echo "3. Тест с Basic Auth:"
    curl -s -u "$USERNAME:$PASSWORD" "$ES_URL/_cat/indices" | head -n 5
    echo ""
    echo ""
fi

# 4. Тест поиска в индексе fias_addresses_v2
echo "4. Тест поиска в индексе fias_addresses_v2:"
SEARCH_CMD="curl -s -X GET \"$ES_URL/fias_addresses_v2/_search\" -H \"Content-Type: application/json\" -d '{\"query\":{\"match\":{\"full_address\":\"Москва\"}},\"size\":3}'"

if [ -n "$API_KEY" ]; then
    SEARCH_CMD="curl -s -H \"Authorization: ApiKey $API_KEY\" -X GET \"$ES_URL/fias_addresses_v2/_search\" -H \"Content-Type: application/json\" -d '{\"query\":{\"match\":{\"full_address\":\"Москва\"}},\"size\":3}'"
elif [ -n "$USERNAME" ] && [ -n "$PASSWORD" ]; then
    SEARCH_CMD="curl -s -u \"$USERNAME:$PASSWORD\" -X GET \"$ES_URL/fias_addresses_v2/_search\" -H \"Content-Type: application/json\" -d '{\"query\":{\"match\":{\"full_address\":\"Москва\"}},\"size\":3}'"
fi

eval $SEARCH_CMD | jq '.hits.total.value, .hits.hits[0]._source.full_address' 2>/dev/null || eval $SEARCH_CMD | head -n 10
echo ""
echo ""

# 5. Проверка статуса кластера
echo "5. Статус кластера:"
STATUS_CMD="curl -s \"$ES_URL/_cluster/health\""

if [ -n "$API_KEY" ]; then
    STATUS_CMD="curl -s -H \"Authorization: ApiKey $API_KEY\" \"$ES_URL/_cluster/health\""
elif [ -n "$USERNAME" ] && [ -n "$PASSWORD" ]; then
    STATUS_CMD="curl -s -u \"$USERNAME:$PASSWORD\" \"$ES_URL/_cluster/health\""
fi

eval $STATUS_CMD | jq '.status, .number_of_nodes, .active_primary_shards' 2>/dev/null || eval $STATUS_CMD | head -n 5
echo ""
echo "=== Тестирование завершено ==="

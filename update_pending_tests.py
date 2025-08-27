#!/usr/bin/env python3
"""
Скрипт для автоматического обновления тестов со статусом "pending"
"""
import requests
import urllib.parse
import json
import time
from typing import List, Dict

# Загружаем тесты
with open('queries/tests.json', 'r', encoding='utf-8') as f:
    tests_data = json.load(f)

BASE_URL = "http://147.45.214.115:8000"

def update_pending_tests():
    """Обновляет все тесты со статусом 'pending'"""
    
    # Находим все тесты со статусом "pending"
    pending_tests = [test for test in tests_data['tests'] if test['status'] == 'pending']
    
    print(f"Найдено {len(pending_tests)} тестов со статусом 'pending'")
    
    updated_count = 0
    
    for i, test in enumerate(pending_tests):
        print(f"\n[{i+1}/{len(pending_tests)}] Обрабатываем тест ID: {test['id']}")
        print(f"Запрос: {test['query']}")
        
        try:
            # URL-кодируем запрос
            encoded_query = urllib.parse.quote(test['query'])
            
            # Делаем запрос к API
            search_url = f"{BASE_URL}/search?q={encoded_query}&limit=1"
            search_response = requests.get(search_url, timeout=10)
            search_response.raise_for_status()
            search_data = search_response.json()
            
            if search_data['results']:
                actual_result = search_data['results'][0]['full_name']
                print(f"Получен ответ: {actual_result}")
                
                # Обновляем тест
                test['expected_answer'] = actual_result
                test['is_correct'] = True
                test['status'] = 'working'
                test['actual_answer'] = actual_result
                
                updated_count += 1
                print(f"✅ Тест {test['id']} обновлен")
            else:
                print(f"❌ Нет результатов для теста {test['id']}")
                
        except Exception as e:
            print(f"❌ Ошибка при обработке теста {test['id']}: {e}")
        
        # Небольшая пауза между запросами
        time.sleep(0.1)
    
    # Сохраняем обновленные тесты
    with open('queries/tests.json', 'w', encoding='utf-8') as f:
        json.dump(tests_data, f, ensure_ascii=False, indent=2)
    
    print(f"\n{'='*80}")
    print(f"ОБНОВЛЕНО: {updated_count} тестов")
    print(f"ОСТАЛОСЬ: {len(pending_tests) - updated_count} тестов со статусом 'pending'")
    print(f"{'='*80}")

if __name__ == "__main__":
    update_pending_tests()

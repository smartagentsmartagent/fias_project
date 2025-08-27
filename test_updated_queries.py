#!/usr/bin/env python3
"""
Скрипт для тестирования обновленных запросов
"""
import requests
import urllib.parse
import json
from typing import List, Dict

# Загружаем тесты
with open('queries/tests.json', 'r', encoding='utf-8') as f:
    tests_data = json.load(f)

# Фильтруем только обновленные тесты (180-184)
updated_tests = [test for test in tests_data['tests'] if test['id'] in [180, 181, 182, 183, 184]]

BASE_URL = "http://147.45.214.115:8000"

def test_query(test: Dict) -> Dict:
    """Тестирует один запрос"""
    print(f"\n{'='*80}")
    print(f"Тест ID: {test['id']}")
    print(f"Запрос: {test['query']}")
    print(f"Ожидаемый ответ: {test['expected_answer']}")
    print(f"{'='*80}")
    
    # URL-кодируем запрос
    encoded_query = urllib.parse.quote(test['query'])
    
    # Поиск
    try:
        search_url = f"{BASE_URL}/search?q={encoded_query}&limit=1"
        search_response = requests.get(search_url, timeout=10)
        search_response.raise_for_status()
        search_data = search_response.json()
        
        if search_data['results']:
            actual_result = search_data['results'][0]['full_name']
            print(f"🔍 Фактический результат: {actual_result}")
            
            # Проверяем соответствие
            if actual_result == test['expected_answer']:
                print("✅ ТЕСТ ПРОЙДЕН")
                return {"status": "passed", "actual": actual_result}
            else:
                print("❌ ТЕСТ НЕ ПРОЙДЕН")
                print(f"   Ожидалось: {test['expected_answer']}")
                print(f"   Получено:  {actual_result}")
                return {"status": "failed", "actual": actual_result}
        else:
            print("❌ Нет результатов")
            return {"status": "no_results"}
            
    except Exception as e:
        print(f"❌ Ошибка: {e}")
        return {"status": "error", "error": str(e)}

def main():
    """Основная функция"""
    print("🚀 Тестирование обновленных запросов")
    print(f"Количество тестов: {len(updated_tests)}")
    
    results = []
    passed = 0
    failed = 0
    
    for test in updated_tests:
        result = test_query(test)
        results.append({"test_id": test['id'], "result": result})
        
        if result['status'] == 'passed':
            passed += 1
        else:
            failed += 1
    
    print(f"\n{'='*80}")
    print("ИТОГИ:")
    print(f"Пройдено: {passed}")
    print(f"Не пройдено: {failed}")
    print(f"Всего: {len(updated_tests)}")
    print(f"{'='*80}")

if __name__ == "__main__":
    main()

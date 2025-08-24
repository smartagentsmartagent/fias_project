#!/usr/bin/env python3
"""
Тест API поиска
"""
import requests
import json

def test_api():
    base_url = "http://localhost:8000"
    
    # Тест health
    print("🔍 Тестируем health endpoint...")
    try:
        response = requests.get(f"{base_url}/health")
        print(f"Health: {response.status_code} - {response.json()}")
    except Exception as e:
        print(f"Ошибка health: {e}")
    
    # Тест поиска
    print("\n🔍 Тестируем поиск...")
    test_queries = [
        "тверская",
        "пл. Савёловского Вокзала, 2",
        "Анадырский пр., 1А"
    ]
    
    for query in test_queries:
        print(f"\n📝 Запрос: '{query}'")
        try:
            response = requests.get(f"{base_url}/search", params={"q": query, "limit": 5})
            print(f"Статус: {response.status_code}")
            
            if response.status_code == 200:
                data = response.json()
                print(f"Результатов: {data.get('total', 0)}")
                if data.get('results'):
                    for i, result in enumerate(data['results'][:3]):
                        print(f"  {i+1}. {result.get('full_name', 'N/A')}")
                else:
                    print("  Нет результатов")
            else:
                print(f"Ошибка: {response.text}")
                
        except Exception as e:
            print(f"Ошибка запроса: {e}")

if __name__ == "__main__":
    test_api()

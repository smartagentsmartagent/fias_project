#!/usr/bin/env python3
"""
Тестовый скрипт для проверки работы поиска FIAS
"""
import requests
import json
import time

def test_search():
    """Тестирование поиска адресов"""
    base_url = "http://localhost:8000"
    
    # Тестовые запросы
    test_queries = [
        "Москва, Варшавское ш., 37с5",
        "Москва, пл. Савёловского Вокзала, 2",
        "Москва, Ореховый бульвар, 39К2",
        "Москва, Свободный проспект, 37/18",
        "Москва, ул. Б Дмитровка, 7/5с2"
    ]
    
    print("🔍 Тестирование поиска FIAS")
    print("=" * 50)
    
    for i, query in enumerate(test_queries, 1):
        print(f"\n{i}. Запрос: {query}")
        
        try:
            # Тест поиска
            response = requests.get(f"{base_url}/search", params={
                "q": query,
                "limit": 3
            })
            
            if response.status_code == 200:
                data = response.json()
                print(f"   ✅ Статус: {response.status_code}")
                print(f"   📊 Найдено результатов: {data.get('total', 0)}")
                
                if data.get('results'):
                    first_result = data['results'][0]
                    print(f"   🏠 Первый результат: {first_result.get('full_name', 'N/A')}")
                    print(f"   📍 Координаты: {first_result.get('geo_point', 'N/A')}")
                else:
                    print("   ❌ Результаты не найдены")
            else:
                print(f"   ❌ Ошибка: {response.status_code}")
                print(f"   📄 Ответ: {response.text}")
                
        except Exception as e:
            print(f"   ❌ Исключение: {e}")
        
        time.sleep(0.5)  # Небольшая пауза между запросами

def test_health():
    """Проверка здоровья API"""
    print("\n🏥 Проверка здоровья API")
    print("=" * 30)
    
    try:
        response = requests.get("http://localhost:8000/health")
        if response.status_code == 200:
            data = response.json()
            print(f"✅ API работает")
            print(f"📊 Elasticsearch: {data.get('elasticsearch', 'unknown')}")
            print(f"📁 Индекс: {data.get('index', 'unknown')}")
        else:
            print(f"❌ API недоступен: {response.status_code}")
    except Exception as e:
        print(f"❌ Ошибка подключения: {e}")

def test_analyze():
    """Тестирование анализа запроса"""
    print("\n🔍 Тестирование анализа запроса")
    print("=" * 40)
    
    test_query = "Москва, Варшавское ш., 37с5"
    
    try:
        response = requests.get(f"http://localhost:8000/analyze", params={
            "q": test_query
        })
        
        if response.status_code == 200:
            data = response.json()
            print(f"📝 Запрос: {test_query}")
            print(f"🔧 Нормализованный: {data.get('normalized_query', 'N/A')}")
            print(f"🏠 Дом: {data.get('house_number', 'N/A')}")
            print(f"🏢 Корпус: {data.get('korpus', 'N/A')}")
            print(f"🏗️ Строение: {data.get('stroenie', 'N/A')}")
        else:
            print(f"❌ Ошибка анализа: {response.status_code}")
    except Exception as e:
        print(f"❌ Исключение: {e}")

if __name__ == "__main__":
    test_health()
    test_analyze()
    test_search()

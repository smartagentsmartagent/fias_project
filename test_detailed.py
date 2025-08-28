#!/usr/bin/env python3
"""
Детальный тестовый скрипт для анализа результатов тестирования FIAS
"""
import requests
import json

def test_detailed_search():
    """Детальное тестирование поиска с анализом результатов"""
    base_url = "http://localhost:8000"
    
    # Тестовые запросы из working.md
    test_queries = [
        "Москва, Варшавское ш., 37с5",
        "Москва, пл. Савёловского Вокзала, 2",
        "Москва, Ореховый бульвар, 39К2",
        "Москва, Свободный проспект, 37/18",
        "Москва, ул. Б Дмитровка, 7/5с2"
    ]
    
    print("🔍 Детальное тестирование поиска FIAS")
    print("=" * 60)
    
    for i, query in enumerate(test_queries, 1):
        print(f"\n{i}. Запрос: {query}")
        print("-" * 50)
        
        try:
            # Тест анализа
            analyze_response = requests.get(f"{base_url}/analyze", params={"q": query})
            if analyze_response.status_code == 200:
                analyze_data = analyze_response.json()
                print(f"🔧 Анализ запроса:")
                print(f"   Нормализованный: {analyze_data.get('normalized_query', 'N/A')}")
                print(f"   Дом: {analyze_data.get('house_number', 'N/A')}")
                print(f"   Корпус: {analyze_data.get('korpus', 'N/A')}")
                print(f"   Строение: {analyze_data.get('stroenie', 'N/A')}")
            
            # Тест поиска
            search_response = requests.get(f"{base_url}/search", params={
                "q": query,
                "limit": 3
            })
            
            if search_response.status_code == 200:
                search_data = search_response.json()
                print(f"\n🔍 Результаты поиска:")
                print(f"   Всего найдено: {search_data.get('total', 0)}")
                
                for j, result in enumerate(search_data.get('results', [])[:3], 1):
                    print(f"   {j}. {result.get('full_name', 'N/A')}")
                    print(f"      Уровень: {result.get('level', 'N/A')}")
                    print(f"      ID: {result.get('id', 'N/A')}")
                    if result.get('geo_point'):
                        geo = result['geo_point']
                        print(f"      Координаты: {geo.get('lat', 'N/A')}, {geo.get('lon', 'N/A')}")
            else:
                print(f"   ❌ Ошибка поиска: {search_response.status_code}")
                
        except Exception as e:
            print(f"   ❌ Исключение: {e}")

def test_automated_tests():
    """Тестирование автоматизированной системы тестов"""
    print("\n\n🧪 Тестирование автоматизированной системы")
    print("=" * 50)
    
    try:
        # Получаем список тестов
        tests_response = requests.get("http://localhost:8000/tests")
        if tests_response.status_code == 200:
            tests_data = tests_response.json()
            total_tests = len(tests_data.get('tests', []))
            print(f"📊 Всего тестов в системе: {total_tests}")
            
            # Запускаем все тесты
            run_response = requests.post("http://localhost:8000/tests/run")
            if run_response.status_code == 200:
                run_data = run_response.json()
                print(f"✅ Тесты выполнены:")
                print(f"   Всего: {run_data.get('total', 0)}")
                print(f"   Прошло: {run_data.get('passed', 0)}")
                print(f"   Провалилось: {run_data.get('failed', 0)}")
                
                # Показываем несколько примеров результатов
                results = run_data.get('results', [])
                print(f"\n📋 Примеры результатов:")
                for i, result in enumerate(results[:5], 1):
                    status = "✅" if result.get('is_correct') else "❌"
                    print(f"   {i}. {status} {result.get('query', 'N/A')}")
                    if not result.get('is_correct'):
                        print(f"      Ожидалось: {result.get('expected', 'N/A')}")
                        print(f"      Получено: {result.get('actual', 'N/A')}")
            else:
                print(f"❌ Ошибка запуска тестов: {run_response.status_code}")
        else:
            print(f"❌ Ошибка получения тестов: {tests_response.status_code}")
            
    except Exception as e:
        print(f"❌ Исключение: {e}")

def test_edge_cases():
    """Тестирование граничных случаев"""
    print("\n\n🔬 Тестирование граничных случаев")
    print("=" * 40)
    
    edge_cases = [
        "Москва",  # Только город
        "Москва, ул. Тверская",  # Без номера дома
        "Москва, ул. Тверская, 1",  # Простой номер
        "Москва, ул. Тверская, 1к1",  # С корпусом
        "Москва, ул. Тверская, 1с1",  # Со строением
        "Москва, ул. Тверская, 1к1с1",  # С корпусом и строением
        "Москва, ул. Тверская, 1/2",  # Дробный номер
        "Москва, ул. Тверская, 1/2к1с1",  # Сложный случай
    ]
    
    for i, query in enumerate(edge_cases, 1):
        print(f"\n{i}. Граничный случай: {query}")
        
        try:
            response = requests.get("http://localhost:8000/search", params={
                "q": query,
                "limit": 1
            })
            
            if response.status_code == 200:
                data = response.json()
                print(f"   ✅ Найдено: {data.get('total', 0)} результатов")
                if data.get('results'):
                    print(f"   🏠 Первый: {data['results'][0].get('full_name', 'N/A')}")
            else:
                print(f"   ❌ Ошибка: {response.status_code}")
                
        except Exception as e:
            print(f"   ❌ Исключение: {e}")

if __name__ == "__main__":
    test_detailed_search()
    test_automated_tests()
    test_edge_cases()

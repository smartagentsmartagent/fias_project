#!/usr/bin/env python3
"""
Простой тест нескольких адресов
"""
import requests
import time

def test_simple():
    base_url = "http://localhost:8000"
    
    # Тестируем несколько адресов
    test_cases = [
        "тверская",
        "пл. Савёловского Вокзала, 2",
        "Варшавское ш., 37с5",
        "пос. Рублёво"
    ]
    
    print("🔍 Простой тест адресов")
    print("=" * 50)
    
    for i, query in enumerate(test_cases, 1):
        print(f"\n[{i}] Тестируем: '{query}'")
        
        try:
            # Добавляем задержку между запросами
            time.sleep(1)
            
            response = requests.get(f"{base_url}/search", params={"q": query, "limit": 3})
            
            if response.status_code == 200:
                data = response.json()
                total = data.get('total', 0)
                print(f"✅ Найдено: {total} результатов")
                
                if data.get('results'):
                    for j, result in enumerate(data['results'][:2], 1):
                        full_name = result.get('full_name', 'N/A')
                        level = result.get('level', 'N/A')
                        print(f"   {j}. [{level}] {full_name}")
                else:
                    print("   ❌ Нет результатов")
            else:
                print(f"❌ Ошибка: {response.status_code}")
                
        except Exception as e:
            print(f"❌ Исключение: {e}")

if __name__ == "__main__":
    test_simple()

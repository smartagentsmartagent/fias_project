#!/usr/bin/env python3
"""
Тест всех проблемных адресов
"""
import requests
import json
from typing import List, Dict

def test_addresses():
    base_url = "http://localhost:8000"
    
    # Все проблемные адреса для тестирования
    test_addresses = [
        "Москва, Северо-Восточный административный округ, Алтуфьевский район, рабочий посёлок Бескудниково",
        "Москва, Варшавское ш., 37с5",
        "Москва, Троицкий административный округ, р-н Бекасово, рп. Киевский, Строительная ул., 14",
        "Москва, Заповедная ул., 16к2с1",
        "Москва, пл. Савёловского Вокзала, 2",
        "Москва, ул. Гризодубовой, 2",
        "Москва, Анадырский пр., 1А",
        "Москва, Варшавское ш., 37с5",
        "Москва, Новомосковский административный округ, р-н Коммунарка, д. Дудкино, СНТ Дудкино, 67",
        "Москва, пос. Рублёво",
        "Москва, Таманская ул., 3с3",
        "Москва, Новосходненское ш., 84с2"
    ]
    
    print("🔍 ТЕСТИРОВАНИЕ ВСЕХ ПРОБЛЕМНЫХ АДРЕСОВ")
    print("=" * 80)
    
    results = []
    
    for i, address in enumerate(test_addresses, 1):
        print(f"\n📝 [{i:2d}] Запрос: '{address}'")
        print("-" * 60)
        
        try:
            response = requests.get(f"{base_url}/search", params={"q": address, "limit": 5})
            
            if response.status_code == 200:
                data = response.json()
                total = data.get('total', 0)
                normalized = data.get('normalized_query', 'N/A')
                house = data.get('house_number', 'N/A')
                
                print(f"✅ Статус: {response.status_code}")
                print(f"📊 Результатов: {total}")
                print(f"🔧 Нормализовано: '{normalized}'")
                print(f"🏠 Дом: {house}")
                
                if data.get('results'):
                    print("📋 Топ результаты:")
                    for j, result in enumerate(data['results'][:3], 1):
                        full_name = result.get('full_name', 'N/A')
                        level = result.get('level', 'N/A')
                        score = result.get('score', 'N/A')
                        print(f"   {j}. [{level}] {full_name} (score: {score})")
                else:
                    print("❌ Нет результатов")
                
                # Сохраняем результат для анализа
                results.append({
                    'address': address,
                    'status': 'success',
                    'total': total,
                    'normalized': normalized,
                    'house': house,
                    'results': data.get('results', [])
                })
                
            else:
                print(f"❌ Ошибка: {response.status_code} - {response.text}")
                results.append({
                    'address': address,
                    'status': 'error',
                    'error': f"{response.status_code}: {response.text}"
                })
                
        except Exception as e:
            print(f"❌ Ошибка запроса: {e}")
            results.append({
                'address': address,
                'status': 'exception',
                'error': str(e)
            })
    
    # Анализ результатов
    print("\n" + "=" * 80)
    print("📊 АНАЛИЗ РЕЗУЛЬТАТОВ")
    print("=" * 80)
    
    successful = [r for r in results if r['status'] == 'success']
    errors = [r for r in results if r['status'] != 'success']
    
    print(f"✅ Успешно обработано: {len(successful)}/{len(results)}")
    print(f"❌ Ошибок: {len(errors)}")
    
    # Проблемные случаи
    print("\n🔍 ПРОБЛЕМНЫЕ СЛУЧАИ:")
    for result in results:
        if result['status'] == 'success':
            if result['total'] == 0:
                print(f"❌ '{result['address']}' - НЕТ РЕЗУЛЬТАТОВ")
            elif result['total'] > 0 and not any('москва' in str(r.get('full_name', '')).lower() for r in result['results']):
                print(f"⚠️  '{result['address']}' - НЕ МОСКВА В РЕЗУЛЬТАТАХ")
    
    return results

if __name__ == "__main__":
    test_addresses()

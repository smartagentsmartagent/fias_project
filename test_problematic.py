#!/usr/bin/env python3
"""
Тестирование проблемных адресов
"""
import requests
import urllib.parse
import json

# Проблемные адреса
PROBLEMATIC_ADDRESSES = [
    "Москва, МКАД, 65-й километр, вл2А",
    "Москва, Северо-Восточный административный округ, Алтуфьевский район, рабочий посёлок Бескудниково",
    "Москва, Троицкий административный округ, р-н Бекасово, рп. Киевский, Строительная ул., 14",
    "Москва, Новомосковский административный округ, р-н Коммунарка, д. Дудкино, СНТ Дудкино, 67"
]

def test_address(address: str, limit: int = 10):
    """Тестирует конкретный адрес"""
    try:
        encoded_query = urllib.parse.quote(address)
        url = f"http://127.0.0.1:8000/search?q={encoded_query}&limit={limit}"
        
        print(f"\n{'='*100}")
        print(f"ТЕСТИРУЕМ: {address}")
        print(f"URL: {url}")
        
        response = requests.get(url, timeout=10)
        
        if response.status_code == 200:
            data = response.json()
            results = data.get('results', [])
            
            print(f"Найдено результатов: {len(results)}")
            
            for i, result in enumerate(results[:5], 1):
                score = result.get('score', 0)
                full_name = result.get('full_name', '')
                house = result.get('house', '')
                korpus = result.get('korpus', '')
                stroenie = result.get('stroenie', '')
                region = result.get('region_norm', '')
                region_code = result.get('region_code', '')
                level = result.get('level', '')
                
                print(f"  {i}. Score: {score:.3f}")
                print(f"     Адрес: {full_name}")
                print(f"     Регион: {region} (code={region_code}), Уровень: {level}")
                print(f"     Дом: {house}, Корпус: {korpus}, Строение: {stroenie}")
                
                # Новые поля
                if 'house_type' in result:
                    print(f"     Тип дома: {result.get('house_type', '')}")
                if 'road_km' in result:
                    print(f"     Км дороги: {result.get('road_km', '')}")
                if 'street_guid' in result:
                    print(f"     GUID улицы: {result.get('street_guid', '')}")
                print()
            
            return {
                'success': True,
                'results_count': len(results),
                'top_result': results[0] if results else None
            }
        else:
            print(f"Ошибка HTTP: {response.status_code}")
            print(f"Ответ: {response.text}")
            return {
                'success': False,
                'error': f"HTTP {response.status_code}"
            }
            
    except Exception as e:
        print(f"Ошибка: {e}")
        return {
            'success': False,
            'error': str(e)
        }

def main():
    print("ТЕСТИРОВАНИЕ ПРОБЛЕМНЫХ АДРЕСОВ")
    print("="*100)
    
    for address in PROBLEMATIC_ADDRESSES:
        result = test_address(address)
        
        if result['success'] and result['results_count'] > 0:
            top_result = result['top_result']
            if top_result:
                region = top_result.get('region_norm', '')
                is_moscow = 'москва' in region.lower()
                print(f"✅ ТОП РЕЗУЛЬТАТ: {'Москва' if is_moscow else 'Другой регион'} - {region}")
        else:
            print("❌ НЕ НАЙДЕНО")

if __name__ == "__main__":
    main()

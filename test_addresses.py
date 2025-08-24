#!/usr/bin/env python3
"""
Скрипт для тестирования поиска по адресам
"""
import requests
import urllib.parse
import json
from typing import List, Dict

# Список адресов для тестирования
ADDRESSES = [
    "Москва, Троицкий административный округ, р-н Бекасово, рп. Киевский, Строительная ул., 14",
    "Москва, Заповедная ул., 16к2с1",
    "Москва, пл. Савёловского Вокзала, 2",
    "Москва, ул. Гризодубовой, 2",
    "Москва, Анадырский пр., 1А",
    "Москва, ул. Гризодубовой, 2",
    "Москва, Дмитровское ш., 122Дк11",
    "Москва, Варшавское ш., 37с5",
    "Москва, ул. Удальцова, 81",
    "Москва, Новомосковский административный округ, р-н Коммунарка, д. Дудкино, СНТ Дудкино, 67",
    "Москва, пос. Рублёво",
    "Москва, Таманская ул., 3с3",
    "Москва, Новосходненское ш., 84с2",
    "Москва, Северо-Восточный административный округ, Алтуфьевский район, рабочий посёлок Бескудниково"
]

BASE_URL = "http://127.0.0.1:8000"

def test_address(address: str) -> Dict:
    """Тестирует один адрес"""
    print(f"\n{'='*80}")
    print(f"Тестируем: {address}")
    print(f"{'='*80}")
    
    # URL-кодируем запрос
    encoded_query = urllib.parse.quote(address)
    
    # Анализ запроса
    try:
        analyze_url = f"{BASE_URL}/analyze?q={encoded_query}"
        analyze_response = requests.get(analyze_url, timeout=10)
        analyze_response.raise_for_status()
        analyze_data = analyze_response.json()
        
        print("📋 Анализ запроса:")
        print(f"   Оригинал: {analyze_data['original']}")
        print(f"   Нормализованный: {analyze_data['normalized']}")
        print(f"   Без дома: {analyze_data['text_without_house']}")
        print(f"   Дом: {analyze_data['house_number']}")
        print(f"   Корпус: {analyze_data['korpus']}")
        print(f"   Строение: {analyze_data['stroenie']}")
        
    except Exception as e:
        print(f"❌ Ошибка анализа: {e}")
        return {"error": str(e)}
    
    # Поиск
    try:
        search_url = f"{BASE_URL}/search?q={encoded_query}&limit=5"
        search_response = requests.get(search_url, timeout=10)
        search_response.raise_for_status()
        search_data = search_response.json()
        
        print(f"\n🔍 Результаты поиска (найдено: {len(search_data['results'])}):")
        
        for i, result in enumerate(search_data['results'][:3], 1):
            print(f"\n   {i}. {result['full_name']}")
            print(f"      ID: {result['id']}")
            print(f"      Уровень: {result['level']}")
            print(f"      Дом: {result['house_number']}")
            print(f"      Корпус: {result['korpus']}")
            print(f"      Строение: {result['stroenie']}")
            if result.get('geo'):
                print(f"      Координаты: {result['geo']['lat']:.6f}, {result['geo']['lon']:.6f}")
            else:
                print(f"      Координаты: не указаны")
            print(f"      Счёт: {result['score']:.2f}")
            
            # Проверяем новые поля
            if result.get('house_type'):
                print(f"      Тип дома: {result['house_type']}")
            if result.get('road_km'):
                print(f"      Км дороги: {result['road_km']}")
            if result.get('street_guid'):
                print(f"      GUID улицы: {result['street_guid']}")
        
        return {
            "analyze": analyze_data,
            "search": search_data,
            "top_result": search_data['results'][0] if search_data['results'] else None
        }
        
    except Exception as e:
        print(f"❌ Ошибка поиска: {e}")
        return {"error": str(e)}

def main():
    """Основная функция"""
    print("🚀 Тестирование поиска адресов в FIAS API")
    print(f"API: {BASE_URL}")
    
    # Проверяем доступность API
    try:
        health_response = requests.get(f"{BASE_URL}/health", timeout=5)
        health_response.raise_for_status()
        health_data = health_response.json()
        print(f"✅ API доступен: {health_data}")
    except Exception as e:
        print(f"❌ API недоступен: {e}")
        return
    
    results = []
    
    for address in ADDRESSES:
        result = test_address(address)
        results.append({
            "address": address,
            "result": result
        })
    
    # Сводка
    print(f"\n{'='*80}")
    print("📊 СВОДКА РЕЗУЛЬТАТОВ")
    print(f"{'='*80}")
    
    successful = 0
    for i, item in enumerate(results, 1):
        address = item["address"]
        result = item["result"]
        
        if "error" in result:
            print(f"{i:2d}. ❌ {address[:50]}... - ОШИБКА")
        else:
            successful += 1
            top_result = result.get("top_result")
            if top_result:
                print(f"{i:2d}. ✅ {address[:50]}... - {top_result['full_name']}")
            else:
                print(f"{i:2d}. ⚠️  {address[:50]}... - НЕТ РЕЗУЛЬТАТОВ")
    
    print(f"\n📈 Итого: {successful}/{len(ADDRESSES)} успешных запросов")

if __name__ == "__main__":
    main()

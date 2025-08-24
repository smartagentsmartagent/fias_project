#!/usr/bin/env python3
import requests
import urllib.parse
import json
from typing import List, Dict

# Проблемные адреса для детального анализа
PROBLEMATIC_ADDRESSES = [
    "Москва, пл. Савёловского Вокзала, 2",
    "Москва, Анадырский пр., 1А",
    "Москва, пос. Рублёво",
    "Москва, Северо-Восточный административный округ, Алтуфьевский район, рабочий посёлок Бескудниково"
]

BASE_URL = "http://127.0.0.1:8000"

def debug_address(address: str):
    """Детальный анализ проблемного адреса"""
    print(f"\n{'='*100}")
    print(f"🔍 ДЕТАЛЬНЫЙ АНАЛИЗ: {address}")
    print(f"{'='*100}")
    
    # URL-кодируем запрос
    encoded_query = urllib.parse.quote(address)
    
    # 1. Анализ запроса
    print("\n📋 1. АНАЛИЗ ЗАПРОСА:")
    try:
        analyze_url = f"{BASE_URL}/analyze?q={encoded_query}"
        analyze_response = requests.get(analyze_url, timeout=10)
        analyze_response.raise_for_status()
        analyze_data = analyze_response.json()
        
        print(f"   Оригинал: {analyze_data['original']}")
        print(f"   Нормализованный: {analyze_data['normalized']}")
        print(f"   Без дома: {analyze_data['text_without_house']}")
        print(f"   Дом: {analyze_data['house_number']}")
        print(f"   Корпус: {analyze_data['korpus']}")
        print(f"   Строение: {analyze_data['stroenie']}")
        
    except Exception as e:
        print(f"❌ Ошибка анализа: {e}")
        return
    
    # 2. Поиск улиц/площадей
    print(f"\n🏛️  2. ПОИСК УЛИЦ/ПЛОЩАДЕЙ:")
    try:
        # Ищем улицы/площади по названию без дома
        street_query = analyze_data['text_without_house']
        if street_query:
            encoded_street = urllib.parse.quote(street_query)
            street_url = f"{BASE_URL}/search?q={encoded_street}&limit=10"
            street_response = requests.get(street_url, timeout=10)
            street_response.raise_for_status()
            street_data = street_response.json()
            
            print(f"   Запрос: '{street_query}'")
            print(f"   Найдено улиц: {len(street_data['results'])}")
            
            for i, result in enumerate(street_data['results'][:5], 1):
                level = result.get('level', 'unknown')
                name = result.get('name', '')
                full_name = result.get('full_name', '')
                score = result.get('score', 0)
                print(f"   {i}. [{level}] {name} - {full_name} (счёт: {score:.2f})")
        
    except Exception as e:
        print(f"❌ Ошибка поиска улиц: {e}")
    
    # 3. Поиск домов
    print(f"\n🏠 3. ПОИСК ДОМОВ:")
    try:
        search_url = f"{BASE_URL}/search?q={encoded_query}&limit=10"
        search_response = requests.get(search_url, timeout=10)
        search_response.raise_for_status()
        search_data = search_response.json()
        
        print(f"   Найдено домов: {len(search_data['results'])}")
        
        for i, result in enumerate(search_data['results'][:5], 1):
            level = result.get('level', 'unknown')
            name = result.get('name', '')
            full_name = result.get('full_name', '')
            score = result.get('score', 0)
            house_num = result.get('house_number', '')
            korpus = result.get('korpus', '')
            stroenie = result.get('stroenie', '')
            
            print(f"   {i}. [{level}] {name} - {full_name}")
            print(f"      Дом: {house_num}, Корпус: {korpus}, Строение: {stroenie}")
            print(f"      Счёт: {score:.2f}")
            
            # Проверяем новые поля
            if result.get('house_type'):
                print(f"      Тип дома: {result['house_type']}")
            if result.get('road_km'):
                print(f"      Км дороги: {result['road_km']}")
            if result.get('street_guid'):
                print(f"      GUID улицы: {result['street_guid']}")
            print()
        
    except Exception as e:
        print(f"❌ Ошибка поиска домов: {e}")
    
    # 4. Специальные проверки
    print(f"\n🔍 4. СПЕЦИАЛЬНЫЕ ПРОВЕРКИ:")
    
    # Проверяем поиск по частям адреса
    parts = address.split(',')
    for i, part in enumerate(parts):
        part = part.strip()
        if part and len(part) > 3:  # Игнорируем короткие части
            try:
                encoded_part = urllib.parse.quote(part)
                part_url = f"{BASE_URL}/search?q={encoded_part}&limit=3"
                part_response = requests.get(part_url, timeout=10)
                part_response.raise_for_status()
                part_data = part_response.json()
                
                if part_data['results']:
                    top_result = part_data['results'][0]
                    print(f"   Часть {i+1}: '{part}' -> {top_result['full_name']} (счёт: {top_result['score']:.2f})")
                
            except Exception as e:
                print(f"   Часть {i+1}: '{part}' -> ошибка: {e}")

def main():
    """Основная функция"""
    print("🔧 ДЕТАЛЬНЫЙ АНАЛИЗ ПРОБЛЕМНЫХ АДРЕСОВ")
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
    
    # Анализируем каждый проблемный адрес
    for address in PROBLEMATIC_ADDRESSES:
        debug_address(address)
    
    print(f"\n{'='*100}")
    print("📊 ЗАКЛЮЧЕНИЕ")
    print(f"{'='*100}")
    print("Основные проблемы:")
    print("1. Отсутствие данных в индексе (Анадырский пр.)")
    print("2. Проблемы с нормализацией (пл. Савёловского Вокзала)")
    print("3. Недостаточная точность для длинных иерархий")
    print("4. Нужно заполнить новые поля (house_type, road_km, *_guid)")

if __name__ == "__main__":
    main()

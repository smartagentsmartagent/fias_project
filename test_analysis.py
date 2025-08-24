#!/usr/bin/env python3
"""
Тестовый скрипт для анализа проблемных запросов
"""
import sys
import os
sys.path.append(os.path.dirname(__file__))

from api.normalizer import normalize_query
from api.search import SearchService
from elasticsearch import Elasticsearch
from config import settings, get_elasticsearch_url

def test_normalizer():
    """Тестирование нормализатора"""
    print("=== ТЕСТИРОВАНИЕ НОРМАЛИЗАТОРА ===")
    
    test_cases = [
        "пл. Савёловского Вокзала, 2",
        "Анадырский пр., 1А",
        "пос. Рублёво",
        "Северо-Восточный административный округ, Алтуфьевский район, рабочий посёлок Бескудниково"
    ]
    
    for query in test_cases:
        print(f"\nЗапрос: {query}")
        try:
            result = normalize_query(query)
            print(f"  Нормализованный: {result['text_without_house']}")
            print(f"  Дом: {result['house_number']}")
            print(f"  Корпус: {result.get('korpus')}")
            print(f"  Строение: {result.get('stroenie')}")
            print(f"  Полный нормализованный: {result.get('normalized')}")
        except Exception as e:
            print(f"  ОШИБКА: {e}")

def test_search():
    """Тестирование поиска"""
    print("\n=== ТЕСТИРОВАНИЕ ПОИСКА ===")
    
    # Подключение к Elasticsearch
    es_client = Elasticsearch([get_elasticsearch_url()])
    search_service = SearchService(es_client, settings.ES_INDEX)
    
    test_cases = [
        "пл. Савёловского Вокзала, 2",
        "Анадырский пр., 1А",
        "пос. Рублёво"
    ]
    
    for query in test_cases:
        print(f"\nЗапрос: {query}")
        try:
            # Нормализация
            normalized = normalize_query(query)
            print(f"  Нормализованный: {normalized['text_without_house']}")
            
            # Поиск
            results = search_service._search_sync(
                query=normalized['text_without_house'],
                house_number=normalized['house_number'],
                korpus=normalized.get('korpus'),
                stroenie=normalized.get('stroenie'),
                limit=3
            )
            
            print(f"  Найдено результатов: {len(results)}")
            for i, result in enumerate(results[:3]):
                print(f"    {i+1}. {result.name_norm} ({result.type_norm}) - {result.full_norm}")
                
        except Exception as e:
            print(f"  ОШИБКА: {e}")

def test_elasticsearch_direct():
    """Прямой запрос к Elasticsearch"""
    print("\n=== ПРЯМОЙ ЗАПРОС К ELASTICSEARCH ===")
    
    es_client = Elasticsearch([get_elasticsearch_url()])
    
    # Поиск площади Савёловского вокзала
    query = {
        "size": 5,
        "query": {
            "bool": {
                "must": [
                    {"term": {"type_norm": "пл"}},
                    {"match": {"name_norm": "савеловского вокзала"}}
                ]
            }
        }
    }
    
    try:
        result = es_client.search(index=settings.ES_INDEX, body=query)
        print(f"Найдено площадей Савёловского вокзала: {len(result['hits']['hits'])}")
        for hit in result['hits']['hits']:
            source = hit['_source']
            print(f"  - {source.get('name_norm')} ({source.get('type_norm')}) - {source.get('full_norm')}")
    except Exception as e:
        print(f"ОШИБКА: {e}")
    
    # Поиск домов на площади Савёловского вокзала
    query = {
        "size": 5,
        "query": {
            "bool": {
                "must": [
                    {"term": {"level": "house"}},
                    {"match": {"full_norm": "савеловского вокзала пл"}}
                ]
            }
        }
    }
    
    try:
        result = es_client.search(index=settings.ES_INDEX, body=query)
        print(f"\nНайдено домов на площади Савёловского вокзала: {len(result['hits']['hits'])}")
        for hit in result['hits']['hits']:
            source = hit['_source']
            print(f"  - Дом {source.get('house_number')} - {source.get('full_norm')}")
    except Exception as e:
        print(f"ОШИБКА: {e}")

if __name__ == "__main__":
    test_normalizer()
    test_search()
    test_elasticsearch_direct()

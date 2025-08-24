#!/usr/bin/env python3
"""
Скрипт для поиска домов на площади Савёловского вокзала
"""
import sys
import os
sys.path.append(os.path.dirname(__file__))

from elasticsearch import Elasticsearch
from config import settings, get_elasticsearch_url

def search_savelyovo_houses():
    """Поиск домов на площади Савёловского вокзала"""
    es_client = Elasticsearch([get_elasticsearch_url()])
    
    print("=== ПОИСК ДОМОВ НА ПЛОЩАДИ САВЁЛОВСКОГО ВОКЗАЛА ===")
    
    # Поиск всех домов на площади Савёловского вокзала
    query = {
        "size": 20,
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
        print(f"Все дома на площади Савёловского вокзала: {len(result['hits']['hits'])} результатов")
        for hit in result['hits']['hits']:
            source = hit['_source']
            print(f"  - Дом {source.get('house_number')} - {source.get('full_norm')}")
    except Exception as e:
        print(f"ОШИБКА: {e}")
    
    # Поиск конкретно дома №2
    query = {
        "size": 5,
        "query": {
            "bool": {
                "must": [
                    {"term": {"level": "house"}},
                    {"term": {"house_number": "2"}},
                    {"match": {"full_norm": "савеловского вокзала"}}
                ]
            }
        }
    }
    
    try:
        result = es_client.search(index=settings.ES_INDEX, body=query)
        print(f"\nПоиск дома №2 на площади Савёловского вокзала: {len(result['hits']['hits'])} результатов")
        for hit in result['hits']['hits']:
            source = hit['_source']
            print(f"  - Дом {source.get('house_number')} - {source.get('full_norm')}")
    except Exception as e:
        print(f"ОШИБКА: {e}")
    
    # Поиск по более широкому запросу
    query = {
        "size": 10,
        "query": {
            "bool": {
                "must": [
                    {"term": {"level": "house"}},
                    {"term": {"house_number": "2"}}
                ],
                "should": [
                    {"match": {"full_norm": "савеловского вокзала"}},
                    {"match": {"full_norm": "савеловск"}}
                ],
                "minimum_should_match": 1
            }
        }
    }
    
    try:
        result = es_client.search(index=settings.ES_INDEX, body=query)
        print(f"\nПоиск дома №2 с упоминанием Савёловского: {len(result['hits']['hits'])} результатов")
        for hit in result['hits']['hits']:
            source = hit['_source']
            print(f"  - Дом {source.get('house_number')} - {source.get('full_norm')}")
    except Exception as e:
        print(f"ОШИБКА: {e}")

if __name__ == "__main__":
    search_savelyovo_houses()

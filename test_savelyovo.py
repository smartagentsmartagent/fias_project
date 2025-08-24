#!/usr/bin/env python3
"""
Специальный скрипт для поиска площади Савёловского вокзала
"""
import sys
import os
sys.path.append(os.path.dirname(__file__))

from elasticsearch import Elasticsearch
from config import settings, get_elasticsearch_url

def search_savelyovo():
    """Поиск площади Савёловского вокзала"""
    es_client = Elasticsearch([get_elasticsearch_url()])
    
    print("=== ПОИСК ПЛОЩАДИ САВЁЛОВСКОГО ВОКЗАЛА ===")
    
    # Поиск по точному названию
    query = {
        "size": 10,
        "query": {
            "match": {
                "name_norm": "савеловского вокзала"
            }
        }
    }
    
    try:
        result = es_client.search(index=settings.ES_INDEX, body=query)
        print(f"Поиск по 'савеловского вокзала': {len(result['hits']['hits'])} результатов")
        for hit in result['hits']['hits']:
            source = hit['_source']
            print(f"  - {source.get('name_norm')} ({source.get('type_norm')}) - {source.get('full_norm')}")
    except Exception as e:
        print(f"ОШИБКА: {e}")
    
    # Поиск по частичному совпадению
    query = {
        "size": 10,
        "query": {
            "match": {
                "name_norm": "савеловск"
            }
        }
    }
    
    try:
        result = es_client.search(index=settings.ES_INDEX, body=query)
        print(f"\nПоиск по 'савеловск': {len(result['hits']['hits'])} результатов")
        for hit in result['hits']['hits']:
            source = hit['_source']
            print(f"  - {source.get('name_norm')} ({source.get('type_norm')}) - {source.get('full_norm')}")
    except Exception as e:
        print(f"ОШИБКА: {e}")
    
    # Поиск по "вокзал"
    query = {
        "size": 10,
        "query": {
            "match": {
                "name_norm": "вокзал"
            }
        }
    }
    
    try:
        result = es_client.search(index=settings.ES_INDEX, body=query)
        print(f"\nПоиск по 'вокзал': {len(result['hits']['hits'])} результатов")
        for hit in result['hits']['hits']:
            source = hit['_source']
            print(f"  - {source.get('name_norm')} ({source.get('type_norm')}) - {source.get('full_norm')}")
    except Exception as e:
        print(f"ОШИБКА: {e}")
    
    # Поиск всех площадей в Москве
    query = {
        "size": 20,
        "query": {
            "bool": {
                "must": [
                    {"term": {"type_norm": "пл"}},
                    {"term": {"region_code": "77"}}
                ]
            }
        }
    }
    
    try:
        result = es_client.search(index=settings.ES_INDEX, body=query)
        print(f"\nВсе площади в Москве: {len(result['hits']['hits'])} результатов")
        for hit in result['hits']['hits']:
            source = hit['_source']
            name = source.get('name_norm', '')
            if 'вокзал' in name.lower():
                print(f"  *** {name} ({source.get('type_norm')}) - {source.get('full_norm')}")
            else:
                print(f"  - {name} ({source.get('type_norm')}) - {source.get('full_norm')}")
    except Exception as e:
        print(f"ОШИБКА: {e}")

if __name__ == "__main__":
    search_savelyovo()

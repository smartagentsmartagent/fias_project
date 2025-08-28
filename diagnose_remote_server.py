#!/usr/bin/env python3
"""
Диагностика проблем с удаленным сервером FIAS
"""
import requests
import json
import time

def check_remote_server():
    """Проверка удаленного сервера"""
    print("🔍 Диагностика удаленного сервера FIAS")
    print("=" * 50)
    
    remote_api = "http://147.45.214.115:8000"
    remote_frontend = "http://147.45.214.115:8080"
    
    # Проверка API
    print(f"\n1. Проверка API: {remote_api}")
    try:
        response = requests.get(f"{remote_api}/health", timeout=10)
        if response.status_code == 200:
            data = response.json()
            print(f"   ✅ API работает")
            print(f"   📊 Elasticsearch: {data.get('elasticsearch', 'unknown')}")
            print(f"   📁 Индекс: {data.get('index', 'unknown')}")
        else:
            print(f"   ❌ API недоступен: {response.status_code}")
    except requests.exceptions.ConnectionError:
        print(f"   ❌ Ошибка подключения к API")
    except requests.exceptions.Timeout:
        print(f"   ⏰ Таймаут подключения к API")
    except Exception as e:
        print(f"   ❌ Ошибка: {e}")
    
    # Проверка фронтенда
    print(f"\n2. Проверка фронтенда: {remote_frontend}")
    try:
        response = requests.get(remote_frontend, timeout=10)
        if response.status_code == 200:
            print(f"   ✅ Фронтенд доступен")
            print(f"   📄 Размер ответа: {len(response.content)} байт")
        else:
            print(f"   ❌ Фронтенд недоступен: {response.status_code}")
    except requests.exceptions.ConnectionError:
        print(f"   ❌ Ошибка подключения к фронтенду")
    except requests.exceptions.Timeout:
        print(f"   ⏰ Таймаут подключения к фронтенду")
    except Exception as e:
        print(f"   ❌ Ошибка: {e}")
    
    # Проверка тестов
    print(f"\n3. Проверка загрузки тестов")
    try:
        response = requests.get(f"{remote_api}/tests", timeout=10)
        if response.status_code == 200:
            data = response.json()
            tests_count = len(data.get('tests', []))
            print(f"   ✅ Тесты загружены: {tests_count} тестов")
        else:
            print(f"   ❌ Ошибка загрузки тестов: {response.status_code}")
    except requests.exceptions.ConnectionError:
        print(f"   ❌ Невозможно загрузить тесты - API недоступен")
    except Exception as e:
        print(f"   ❌ Ошибка: {e}")

def check_local_services():
    """Проверка локальных сервисов"""
    print(f"\n\n🏠 Диагностика локальных сервисов")
    print("=" * 40)
    
    local_api = "http://localhost:8000"
    local_frontend = "http://localhost:8080"
    
    # Проверка локального API
    print(f"\n1. Проверка локального API: {local_api}")
    try:
        response = requests.get(f"{local_api}/health", timeout=5)
        if response.status_code == 200:
            data = response.json()
            print(f"   ✅ Локальный API работает")
            print(f"   📊 Elasticsearch: {data.get('elasticsearch', 'unknown')}")
        else:
            print(f"   ❌ Локальный API недоступен: {response.status_code}")
    except Exception as e:
        print(f"   ❌ Ошибка: {e}")
    
    # Проверка локального фронтенда
    print(f"\n2. Проверка локального фронтенда: {local_frontend}")
    try:
        response = requests.get(local_frontend, timeout=5)
        if response.status_code == 200:
            print(f"   ✅ Локальный фронтенд работает")
            print(f"   📄 Размер ответа: {len(response.content)} байт")
        else:
            print(f"   ❌ Локальный фронтенд недоступен: {response.status_code}")
    except Exception as e:
        print(f"   ❌ Ошибка: {e}")

def compare_services():
    """Сравнение локальных и удаленных сервисов"""
    print(f"\n\n📊 Сравнение сервисов")
    print("=" * 30)
    
    services = [
        ("API", "http://localhost:8000/health", "http://147.45.214.115:8000/health"),
        ("Фронтенд", "http://localhost:8080/", "http://147.45.214.115:8080/"),
        ("Тесты", "http://localhost:8000/tests", "http://147.45.214.115:8000/tests")
    ]
    
    for name, local_url, remote_url in services:
        print(f"\n{name}:")
        
        # Локальный
        try:
            local_response = requests.get(local_url, timeout=5)
            local_status = "✅" if local_response.status_code == 200 else "❌"
            print(f"   Локальный: {local_status} {local_response.status_code}")
        except:
            print(f"   Локальный: ❌ недоступен")
        
        # Удаленный
        try:
            remote_response = requests.get(remote_url, timeout=10)
            remote_status = "✅" if remote_response.status_code == 200 else "❌"
            print(f"   Удаленный: {remote_status} {remote_response.status_code}")
        except:
            print(f"   Удаленный: ❌ недоступен")

def provide_solutions():
    """Предоставление решений"""
    print(f"\n\n💡 Рекомендации по решению проблем")
    print("=" * 40)
    
    print(f"\n1. Проблема: Удаленный API недоступен")
    print(f"   Решение: Используйте локальную версию")
    print(f"   Команды:")
    print(f"   - API: python -m uvicorn api.main:app --host 0.0.0.0 --port 8000 --reload")
    print(f"   - Фронтенд: python -m http.server 8080 --directory frontend")
    
    print(f"\n2. Проблема: Тесты не загружаются")
    print(f"   Решение: Проверьте подключение к Elasticsearch")
    print(f"   Проверка: curl http://localhost:8000/health")
    
    print(f"\n3. Проблема: Поиск не работает")
    print(f"   Решение: Убедитесь что API запущен и доступен")
    print(f"   Тест: curl 'http://localhost:8000/search?q=Москва&limit=1'")
    
    print(f"\n4. Альтернативное решение:")
    print(f"   Используйте локальный веб-интерфейс: http://localhost:8080/")
    print(f"   Он будет работать с локальным API на порту 8000")

if __name__ == "__main__":
    check_remote_server()
    check_local_services()
    compare_services()
    provide_solutions()

"""
FastAPI приложение для адресного поиска FIAS
"""
import asyncio
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from typing import List, Dict, Any, Optional
import logging
from elasticsearch import Elasticsearch
from pathlib import Path

import sys
import os
import json
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

from config import settings, get_elasticsearch_config
from .normalizer import normalize_query
from .search import SearchService
from .models import SearchResponse, AddressItem

# Настройка логирования
logging.basicConfig(level=getattr(logging, settings.LOG_LEVEL))
logger = logging.getLogger(__name__)

# Создание FastAPI приложения
app = FastAPI(
    title="FIAS Адресный поиск",
    description="API для поиска адресов FIAS",
    version="2.0.0"
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Глобальные переменные для сервисов
es_client = None
search_service = None


@app.on_event("startup")
async def startup_event():
    """Инициализация при запуске"""
    global es_client, search_service
    
    try:
        # Подключение к Elasticsearch
        es_config = get_elasticsearch_config()
        es_client = Elasticsearch(
            **es_config
        )
        
        # Проверка подключения
        if not es_client.ping():
            raise Exception("Не удалось подключиться к Elasticsearch")
        
        # Инициализация сервиса поиска
        search_service = SearchService(es_client, settings.ES_INDEX)
        
        logger.info("API успешно инициализировано")
        
    except Exception as e:
        logger.error(f"Ошибка инициализации: {e}")
        raise


@app.on_event("shutdown")
async def shutdown_event():
    """Очистка при завершении"""
    if es_client:
        es_client.close()


@app.get("/", response_model=dict)
async def root():
    """Корневой эндпоинт"""
    return {
        "message": "FIAS Адресный поиск API",
        "version": "2.0.0",
        "status": "running",
        "docs": "/docs"
    }


@app.get("/health")
async def health_check():
    """Проверка здоровья сервиса"""
    try:
        # Простая проверка без проблемных вызовов
        status = {
            "status": "healthy",
            "elasticsearch": "unknown",
            "index": settings.ES_INDEX,
            "index_exists": False
        }
        
        if es_client:
            try:
                # Простой запрос к индексу
                result = es_client.cat.indices(index=settings.ES_INDEX, format="json")
                if result:
                    status["elasticsearch"] = "connected"
                    status["index_exists"] = True
            except:
                status["elasticsearch"] = "disconnected"
        
        return status
    except Exception as e:
        logger.error(f"Ошибка проверки здоровья: {e}")
        return {"status": "error", "message": str(e)}


@app.get("/search", response_model=SearchResponse)
async def search_addresses(
    q: str = Query(..., description="Поисковый запрос"),
    limit: int = Query(10, ge=1, le=100, description="Максимальное количество результатов")
):
    """Поиск адресов"""
    try:
        if not search_service:
            raise HTTPException(status_code=503, detail="Сервис поиска не инициализирован")
        
        # Нормализация запроса
        normalized = normalize_query(q)
        logger.info(
            f"Поиск: '{q}' -> '{normalized['text_without_house']}', "
            f"дом={normalized['house_number']}, корп={normalized.get('korpus')}, стр={normalized.get('stroenie')}"
        )
        
        # Поиск
        # Сформируем расширенную фразу для точного матча по full_norm
        expanded_phrase = normalized['text_without_house']
        if normalized['house_number']:
            expanded_phrase = f"{expanded_phrase} дом {normalized['house_number']}"
            if normalized.get('korpus'):
                expanded_phrase = f"{expanded_phrase} к {normalized['korpus']}"
            if normalized.get('stroenie'):
                expanded_phrase = f"{expanded_phrase} с {normalized['stroenie']}"

        results = await search_service.search(
            query=normalized['text_without_house'],
            house_number=normalized['house_number'],
            korpus=normalized.get('korpus'),
            stroenie=normalized.get('stroenie'),
            limit=limit,
            full_phrase=normalized.get('normalized') or q,
            expanded_phrase=expanded_phrase,
            has_moscow=normalized.get('has_moscow', False),
            has_moscow_region=normalized.get('has_moscow_region', False),
            has_balashikha=normalized.get('has_balashikha', False),
            has_leningrad_region=normalized.get('has_leningrad_region', False),
            original_query=q
        )
        
        return SearchResponse(
            query=q,
            normalized_query=normalized['text_without_house'],
            house_number=normalized['house_number'],
            total=len(results),
            results=results
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Ошибка поиска: {e}")
        raise HTTPException(status_code=500, detail="Ошибка выполнения поиска")


@app.get("/suggest", response_model=List[AddressItem])
async def suggest_addresses(
    q: str = Query(..., description="Поисковый запрос для подсказок"),
    limit: int = Query(5, ge=1, le=20, description="Максимальное количество подсказок")
):
    """Подсказки адресов (упрощенная версия поиска)"""
    try:
        if not search_service:
            raise HTTPException(status_code=503, detail="Сервис поиска не инициализирован")
        
        # Нормализация запроса
        normalized = normalize_query(q)
        
        # Поиск только по названию без домов
        results = await search_service.search(
            query=normalized['text_without_house'],
            house_number=None,
            limit=limit
        )
        
        return results
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Ошибка получения подсказок: {e}")
        raise HTTPException(status_code=500, detail="Ошибка получения подсказок")


@app.get("/analyze", response_model=dict)
async def analyze_query(q: str = Query(..., description="Запрос для анализа")):
    """Анализ поискового запроса"""
    try:
        normalized = normalize_query(q)
        return normalized
    except Exception as e:
        logger.error(f"Ошибка анализа запроса: {e}")
        raise HTTPException(status_code=500, detail="Ошибка анализа запроса")


@app.get("/etl-status")
async def etl_status():
    """Статус ETL процесса"""
    try:
        # Получаем количество документов в индексе
        if not es_client:
            return {"status": "error", "message": "Elasticsearch недоступен"}
        
        try:
            count_result = es_client.count(index=settings.ES_INDEX)
            total_docs = count_result.get('count', 0) if isinstance(count_result, dict) else count_result.body.get('count', 0)
        except:
            total_docs = 0
            
        # Примерное общее количество записей в базе данных (из резюме: 38M записей)
        total_estimated = 38209622
        progress_percent = min(100, (total_docs / total_estimated) * 100) if total_estimated > 0 else 0
        
        return {
            "status": "running" if total_docs < total_estimated else "completed",
            "total_docs": total_docs,
            "total_estimated": total_estimated,
            "progress_percent": round(progress_percent, 2),
            "message": f"Загружено {total_docs:,} из ~{total_estimated:,} записей"
        }
    except Exception as e:
        logger.error(f"Ошибка получения статуса ETL: {e}")
        return {"status": "error", "message": str(e)}


def load_tests():
    """Загрузка тестов из файла"""
    try:
        # Используем абсолютный путь через Path
        tests_file = Path(__file__).resolve().parents[1] / "queries" / "tests.json"
        logger.info(f"Загружаем тесты из файла: {tests_file}")
        logger.info(f"Файл существует: {tests_file.exists()}")
        
        with open(tests_file, 'r', encoding='utf-8') as f:
            data = json.load(f)
            logger.info(f"Загружено тестов: {len(data.get('tests', []))}")
            logger.info(f"Структура данных: {list(data.keys())}")
            return data
    except FileNotFoundError as e:
        logger.error(f"Файл тестов не найден: {e}")
        return {"tests": []}
    except json.JSONDecodeError as e:
        logger.error(f"Ошибка парсинга JSON в файле тестов: {e}")
        return {"tests": []}
    except Exception as e:
        logger.error(f"Ошибка загрузки тестов: {e}")
        logger.error(f"Текущая директория: {os.getcwd()}")
        return {"tests": []}


def save_tests(tests_data):
    """Сохранение тестов в файл"""
    try:
        tests_file = Path(__file__).resolve().parents[1] / "queries" / "tests.json"
        with open(tests_file, 'w', encoding='utf-8') as f:
            json.dump(tests_data, f, ensure_ascii=False, indent=2)
        return True
    except Exception as e:
        logger.error(f"Ошибка сохранения тестов: {e}")
        return False


@app.get("/tests")
async def get_tests():
    """Получение списка всех тестов"""
    try:
        tests_data = load_tests()
        return tests_data
    except Exception as e:
        logger.error(f"Ошибка получения тестов: {e}")
        raise HTTPException(status_code=500, detail="Ошибка получения тестов")


@app.post("/tests")
async def add_test(test_data: dict):
    """Добавление нового теста"""
    try:
        tests_data = load_tests()
        
        # Генерируем новый ID
        new_id = max([test.get('id', 0) for test in tests_data['tests']], default=0) + 1
        
        new_test = {
            "id": new_id,
            "query": test_data.get('query', ''),
            "expected_answer": test_data.get('expected_answer', ''),
            "is_correct": test_data.get('is_correct', False),
            "status": test_data.get('status', 'pending')
        }
        
        tests_data['tests'].append(new_test)
        
        if save_tests(tests_data):
            return {"message": "Тест добавлен", "test": new_test}
        else:
            raise HTTPException(status_code=500, detail="Ошибка сохранения теста")
            
    except Exception as e:
        logger.error(f"Ошибка добавления теста: {e}")
        raise HTTPException(status_code=500, detail="Ошибка добавления теста")


@app.put("/tests/{test_id}")
async def update_test(test_id: int, test_data: dict):
    """Обновление теста"""
    try:
        tests_data = load_tests()
        
        for test in tests_data['tests']:
            if test['id'] == test_id:
                test.update({
                    "query": test_data.get('query', test['query']),
                    "expected_answer": test_data.get('expected_answer', test['expected_answer']),
                    "is_correct": test_data.get('is_correct', test['is_correct']),
                    "status": test_data.get('status', test['status'])
                })
                
                if save_tests(tests_data):
                    return {"message": "Тест обновлен", "test": test}
                else:
                    raise HTTPException(status_code=500, detail="Ошибка сохранения теста")
        
        raise HTTPException(status_code=404, detail="Тест не найден")
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Ошибка обновления теста: {e}")
        raise HTTPException(status_code=500, detail="Ошибка обновления теста")


@app.delete("/tests/{test_id}")
async def delete_test(test_id: int):
    """Удаление теста"""
    try:
        tests_data = load_tests()
        
        for i, test in enumerate(tests_data['tests']):
            if test['id'] == test_id:
                deleted_test = tests_data['tests'].pop(i)
                
                if save_tests(tests_data):
                    return {"message": "Тест удален", "test": deleted_test}
                else:
                    raise HTTPException(status_code=500, detail="Ошибка сохранения тестов")
        
        raise HTTPException(status_code=404, detail="Тест не найден")
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Ошибка удаления теста: {e}")
        raise HTTPException(status_code=500, detail="Ошибка удаления теста")


@app.post("/tests/run")
async def run_tests():
    """Запуск всех тестов и обновление статусов"""
    try:
        if not search_service:
            raise HTTPException(status_code=503, detail="Сервис поиска не инициализирован")
        
        tests_data = load_tests()
        logger.info(f"Загружено тестов: {len(tests_data.get('tests', []))}")
        logger.info(f"Структура данных: {list(tests_data.keys())}")
        logger.info(f"tests_data type: {type(tests_data)}")
        logger.info(f"tests_data content: {tests_data}")
        results = []
        
        # Проверяем структуру данных
        if 'tests' not in tests_data or not tests_data['tests']:
            logger.error("Нет тестов в данных")
            logger.error(f"tests_data: {tests_data}")
            logger.error(f"tests_data type: {type(tests_data)}")
            return {
                "message": "Нет тестов для выполнения",
                "total": 0,
                "passed": 0,
                "failed": 0,
                "results": []
            }
        
        # Ограничиваем количество одновременных запросов
        import asyncio
        import time
        
        # Обрабатываем тесты пакетами по 10 штук с задержкой
        batch_size = 10
        delay_between_batches = 0.5  # секунды
        
        logger.info(f"Начинаем обработку {len(tests_data['tests'])} тестов пакетами по {batch_size}")
        
        for i in range(0, len(tests_data['tests']), batch_size):
            batch = tests_data['tests'][i:i + batch_size]
            
            # Создаем задачи для пакета
            tasks = []
            for test in batch:
                task = asyncio.create_task(process_single_test(test))
                tasks.append(task)
            
            # Выполняем пакет с таймаутом
            try:
                batch_results = await asyncio.wait_for(
                    asyncio.gather(*tasks, return_exceptions=True),
                    timeout=30.0  # таймаут на пакет
                )
                
                for result in batch_results:
                    if isinstance(result, Exception):
                        logger.error(f"Ошибка в пакете тестов: {result}")
                        # Добавляем ошибку для теста
                        continue
                    results.append(result)
                    
            except asyncio.TimeoutError:
                logger.error(f"Таймаут при выполнении пакета тестов {i//batch_size + 1}")
                # Добавляем ошибки для невыполненных тестов
                for test in batch:
                    results.append({
                        "id": test['id'],
                        "query": test['query'],
                        "expected": test['expected_answer'],
                        "actual": "Таймаут выполнения",
                        "is_correct": False,
                        "error": "timeout"
                    })
            
            # Задержка между пакетами
            if i + batch_size < len(tests_data['tests']):
                await asyncio.sleep(delay_between_batches)
        
        # Обновляем тесты с результатами
        for result in results:
            for test in tests_data['tests']:
                if test['id'] == result['id']:
                    test['is_correct'] = result['is_correct']
                    test['actual_answer'] = result['actual']
                    if 'error' in result:
                        test['error'] = result['error']
                    break
        
        # Сохраняем обновленные тесты
        if save_tests(tests_data):
            return {
                "message": "Тесты выполнены",
                "total": len(results),
                "passed": len([r for r in results if r['is_correct']]),
                "failed": len([r for r in results if not r['is_correct']]),
                "results": results
            }
        else:
            raise HTTPException(status_code=500, detail="Ошибка сохранения результатов тестов")
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Ошибка выполнения тестов: {e}")
        raise HTTPException(status_code=500, detail="Ошибка выполнения тестов")


async def process_single_test(test):
    """Обработка одного теста с таймаутом"""
    try:
        # Нормализация запроса как в основном эндпоинте
        normalized = normalize_query(test['query'])
        
        # Сформируем расширенную фразу для точного матча по full_norm
        expanded_phrase = normalized['text_without_house']
        if normalized['house_number']:
            expanded_phrase = f"{expanded_phrase} дом {normalized['house_number']}"
            if normalized.get('korpus'):
                expanded_phrase = f"{expanded_phrase} к {normalized['korpus']}"
            if normalized.get('stroenie'):
                expanded_phrase = f"{expanded_phrase} с {normalized['stroenie']}"

        # Выполняем поиск с таймаутом
        response = await asyncio.wait_for(
            search_service.search(
                query=normalized['text_without_house'],
                house_number=normalized['house_number'],
                korpus=normalized.get('korpus'),
                stroenie=normalized.get('stroenie'),
                limit=1,
                full_phrase=normalized.get('normalized') or test['query'],
                expanded_phrase=expanded_phrase,
                has_moscow=normalized.get('has_moscow', False),
                has_moscow_region=normalized.get('has_moscow_region', False),
                has_balashikha=normalized.get('has_balashikha', False),
                has_leningrad_region=normalized.get('has_leningrad_region', False),
                original_query=test['query']
            ),
            timeout=5.0  # таймаут на один запрос
        )
        
        # Получаем первый результат
        actual_answer = ""
        if response and len(response) > 0:
            actual_answer = response[0].full_name
        
        # Проверяем корректность
        expected = test['expected_answer']
        # Если ожидается null (пустой результат), то actual_answer должен быть пустым
        if expected is None or expected == "":
            is_correct = actual_answer == "" or actual_answer is None
        else:
            is_correct = actual_answer == expected
        
        return {
            "id": test['id'],
            "query": test['query'],
            "expected": test['expected_answer'],
            "actual": actual_answer,
            "is_correct": is_correct
        }
        
    except asyncio.TimeoutError:
        logger.error(f"Таймаут выполнения теста {test['id']}: {test['query']}")
        return {
            "id": test['id'],
            "query": test['query'],
            "expected": test['expected_answer'],
            "actual": "Таймаут выполнения",
            "is_correct": False,
            "error": "timeout"
        }
    except ConnectionError as e:
        logger.error(f"Ошибка подключения к Elasticsearch в тесте {test['id']}: {e}")
        return {
            "id": test['id'],
            "query": test['query'],
            "expected": test['expected_answer'],
            "actual": "Ошибка подключения к Elasticsearch",
            "is_correct": False,
            "error": "elasticsearch_connection"
        }
    except Exception as e:
        logger.error(f"Ошибка выполнения теста {test['id']}: {e}")
        return {
            "id": test['id'],
            "query": test['query'],
            "expected": test['expected_answer'],
            "actual": f"Ошибка: {str(e)}",
            "is_correct": False,
            "error": "general"
        }


# Обработчик глобальных ошибок
@app.exception_handler(Exception)
async def global_exception_handler(request, exc):
    logger.error(f"Необработанная ошибка: {exc}")
    return JSONResponse(
        status_code=500,
        content={"detail": "Внутренняя ошибка сервера"}
    )


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "main:app",
        host=settings.API_HOST,
        port=settings.API_PORT,
        reload=settings.API_DEBUG
    )

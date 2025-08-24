"""
ETL скрипт для загрузки данных FIAS из MySQL в Elasticsearch
"""
import mysql.connector
from elasticsearch import Elasticsearch
from elasticsearch.helpers import bulk
import logging
import time
from typing import Dict, Any, Iterator, List, Optional
from tqdm import tqdm

import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config import settings, get_elasticsearch_url, get_mysql_url
import re

# Настройка логирования
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class FiasETL:
    """ETL процесс для загрузки данных FIAS"""
    
    def __init__(self, region_codes: Optional[List[int]] = None, recreate_index: bool = True):
        self.es = Elasticsearch([get_elasticsearch_url()])
        self.mysql_config = {
            'host': settings.MYSQL_HOST,
            'port': settings.MYSQL_PORT,
            'user': settings.MYSQL_USER,
            'password': settings.MYSQL_PASSWORD,
            'database': settings.MYSQL_DATABASE,
            'charset': 'utf8mb4'
        }
        self.region_codes = region_codes
        self.recreate_index = recreate_index
    
    def create_index(self) -> bool:
        """Создание индекса в Elasticsearch"""
        try:
            # Удаляем индекс если существует и требуется пересоздать
            if self.recreate_index and self.es.indices.exists(index=settings.ES_INDEX):
                logger.info(f"Удаляем существующий индекс {settings.ES_INDEX}")
                self.es.indices.delete(index=settings.ES_INDEX)
            
            # Маппинг индекса
            mapping = {
                "mappings": {
                    "properties": {
                        "level": {
                            "type": "keyword"
                        },
                        "name_norm": {
                            "type": "text",
                            "analyzer": "standard",
                            "fields": {
                                "keyword": {
                                    "type": "keyword"
                                }
                            }
                        },
                        "name_exact": {
                            "type": "keyword"
                        },
                        "type_norm": {
                            "type": "keyword"
                        },
                        "full_norm": {
                            "type": "text",
                            "analyzer": "standard"
                        },
                        "region_code": {
                            "type": "keyword"
                        },
                        "geo": {
                            "type": "geo_point"
                        },
                        "house_number": {
                            "type": "keyword"
                        },
                        "korpus": {
                            "type": "keyword"
                        },
                        "stroenie": {
                            "type": "keyword"
                        }
                    }
                },
                "settings": {
                    "number_of_shards": 1,
                    "number_of_replicas": 0,
                    "refresh_interval": "30s"
                }
            }
            
            # Создаем индекс, если он отсутствует
            if not self.es.indices.exists(index=settings.ES_INDEX):
                self.es.indices.create(index=settings.ES_INDEX, body=mapping)
                logger.info(f"Индекс {settings.ES_INDEX} создан успешно")
            return True
            
        except Exception as e:
            logger.error(f"Ошибка создания индекса: {e}")
            return False
    
    def get_data_from_mysql(self) -> Iterator[Dict[str, Any]]:
        """Получение данных из MySQL"""
        try:
            connection = mysql.connector.connect(**self.mysql_config)
            cursor = connection.cursor(dictionary=True)
            
            # Запрос для получения адресных данных из address_table2
            base_query = """
            SELECT 
                guid as id,
                CASE 
                    WHEN level = 0 THEN 'region'
                    WHEN level = 3 THEN 'city'
                    WHEN level = 7 THEN 'street'
                    WHEN level = 8 THEN 'house'
                    ELSE 'other'
                END as level,
                LOWER(name) as name_norm,
                name as name_exact,
                LOWER(short_name) as type_norm,
                LOWER(text_cache) as full_norm,
                region_code,
                CASE 
                    WHEN level = 8 THEN name
                    ELSE NULL
                END as house_number,
                corpus as korpus,
                building as stroenie,
                lat,
                lon
            FROM address_table2 
            WHERE 
                status IN (0, 2)  -- Актуальные записи (0 - актуальные, 2 - актуальные с изменениями)
                AND level IN (0, 3, 7, 8)  -- Основные уровни: регион, город, улица, дом
                AND name IS NOT NULL
                AND name != ''
            """

            params: List[Any] = []
            where_extras = []
            if self.region_codes:
                placeholders = ", ".join(["%s"] * len(self.region_codes))
                where_extras.append(f"region_code IN ({placeholders})")
                params.extend(self.region_codes)

            order_by = " ORDER BY level, name"
            query = base_query
            if where_extras:
                query += " AND " + " AND ".join(where_extras)
            query += order_by
            
            logger.info("Выполняем запрос к MySQL...")
            cursor.execute(query, tuple(params))
            
            batch_size = 1000
            while True:
                batch = cursor.fetchmany(batch_size)
                if not batch:
                    break
                
                for row in batch:
                    # Преобразуем данные для Elasticsearch
                    doc = {
                        '_index': settings.ES_INDEX,
                        '_id': row['id'],
                        '_source': {
                            'level': row['level'],
                            'name_norm': row['name_norm'],
                            'name_exact': row['name_exact'],
                            'type_norm': row['type_norm'],
                            'full_norm': row['full_norm'],
                            'region_code': str(row['region_code']) if row['region_code'] else None
                        }
                    }
                    
                    # Добавляем координаты если есть
                    if row['lat'] and row['lon']:
                        doc['_source']['geo'] = {
                            'lat': float(row['lat']),
                            'lon': float(row['lon'])
                        }
                    
                    # Добавляем данные дома если есть
                    if row['house_number']:
                        house_number = str(row['house_number']).lower()
                        korpus = (str(row['korpus']).lower() if row['korpus'] else None)
                        stroenie = (str(row['stroenie']).lower() if row['stroenie'] else None)

                        # Если в БД корпус/строение не заполнены, попробуем распарсить из компактной формы имени дома
                        # Поддержка: "49к4", "49 к 4", "49к4с2", "49с2", алиасы к/корп/корпус, с/стр/строение
                        if (not korpus) or (not stroenie):
                            name_for_parse = house_number
                            name_for_parse = re.sub(r'k', 'к', name_for_parse)
                            name_for_parse = re.sub(r'c', 'с', name_for_parse)
                            # Вставим пробелы между числом и метками
                            name_for_parse = re.sub(r'(\d)\s*[к]\s*(\d)', r'\1 к \2', name_for_parse)
                            name_for_parse = re.sub(r'(\d)\s*[с]\s*(\d)', r'\1 с \2', name_for_parse)

                            corp_alias = r'(?:корпус|корп|кор\.?|к)'
                            bldg_alias = r'(?:строение|стр\.?|с)'
                            own_alias = r'(?:владение|влад\.?|вл)'

                            base_num = r'(?:дом|д)?\.?\s*(\d+[абвгдежзийклмнопрстуфхцчшщъыьэюя]?)'
                            corp_num = r'(?:\s*(?:' + corp_alias + r')\.?\s*(\d+[абвгдежзийклмнопрстуфхцчшщъыьэюя]?))'
                            bldg_num = r'(?:\s*(?:' + bldg_alias + r'|' + own_alias + r')\.?\s*(\d+[абвгдежзийклмнопрстуфхцчшщъыьэюя]?))'

                            pattern1 = re.compile(r'^' + base_num + r'(?:' + corp_num + r')?(?:' + bldg_num + r')?$', re.IGNORECASE)
                            pattern2 = re.compile(r'^' + base_num + r'(?:' + bldg_num + r')?(?:' + corp_num + r')?$', re.IGNORECASE)

                            m = pattern1.search(name_for_parse) or pattern2.search(name_for_parse)
                            if m:
                                house_number = m.group(1)
                                if not korpus and len(m.groups()) >= 2:
                                    korpus = m.group(2)
                                if not stroenie and len(m.groups()) >= 3:
                                    stroenie = m.group(3)

                        doc['_source']['house_number'] = house_number
                        if korpus:
                            doc['_source']['korpus'] = korpus
                        if stroenie:
                            doc['_source']['stroenie'] = stroenie
                    
                    yield doc
            
            cursor.close()
            connection.close()
            
        except Exception as e:
            logger.error(f"Ошибка получения данных из MySQL: {e}")
    
    def load_data(self) -> bool:
        """Загрузка данных в Elasticsearch"""
        try:
            logger.info("Начинаем загрузку данных...")
            
            # Получаем данные и загружаем пакетами
            docs = self.get_data_from_mysql()
            
            # Используем bulk loading для эффективности
            success_count, failed_count = bulk(
                self.es,
                docs,
                chunk_size=500,
                request_timeout=60,
                max_retries=3,
                initial_backoff=2,
                max_backoff=600
            )
            
            logger.info(f"Загружено документов: {success_count}")
            if failed_count:
                logger.warning(f"Ошибок при загрузке: {len(failed_count)}")
            
            # Обновляем индекс
            self.es.indices.refresh(index=settings.ES_INDEX)
            
            return True
            
        except Exception as e:
            logger.error(f"Ошибка загрузки данных: {e}")
            return False
    
    def run_etl(self) -> bool:
        """Запуск полного ETL процесса"""
        logger.info("Запуск ETL процесса FIAS")
        
        start_time = time.time()
        
        # Проверяем подключение к Elasticsearch
        if not self.es.ping():
            logger.error("Не удалось подключиться к Elasticsearch")
            return False
        
        # Создаем индекс (при необходимости)
        if not self.create_index():
            return False
        
        # Загружаем данные
        if not self.load_data():
            return False
        
        # Получаем статистику
        stats = self.es.indices.stats(index=settings.ES_INDEX)
        doc_count = stats['indices'][settings.ES_INDEX]['total']['docs']['count']
        
        elapsed_time = time.time() - start_time
        logger.info(f"ETL завершен успешно за {elapsed_time:.2f} секунд")
        logger.info(f"Загружено документов: {doc_count}")
        
        return True


if __name__ == "__main__":
    etl = FiasETL()
    success = etl.run_etl()
    
    if success:
        print("✅ ETL процесс завершен успешно")
    else:
        print("❌ ETL процесс завершился с ошибкой")
        exit(1)

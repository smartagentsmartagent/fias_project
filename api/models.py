"""
Модели данных для API
"""
from typing import List, Optional, Dict, Any
from pydantic import BaseModel


class GeoPoint(BaseModel):
    """Географические координаты"""
    lat: float
    lon: float


class AddressItem(BaseModel):
    """Элемент адреса в результатах поиска"""
    id: str
    level: str  # region, city, street, house
    name: str
    full_name: str
    region_code: Optional[str] = None
    geo: Optional[GeoPoint] = None
    score: Optional[float] = None
    
    # Нормализованные поля из индекса
    name_norm: Optional[str] = None
    name_exact: Optional[str] = None
    full_norm: Optional[str] = None
    type_norm: Optional[str] = None
    name_lem: Optional[str] = None
    
    # Дополнительные поля для домов
    house_number: Optional[str] = None
    korpus: Optional[str] = None
    stroenie: Optional[str] = None
    
    # Новые поля из расширенного индекса
    house_type: Optional[str] = None  # владение/строение/сооружение/литера
    road_km: Optional[int] = None     # километр для МКАД/КАД
    street_guid: Optional[str] = None
    settlement_guid: Optional[str] = None
    city_guid: Optional[str] = None


class SearchResponse(BaseModel):
    """Ответ на поисковый запрос"""
    query: str
    normalized_query: str
    house_number: Optional[str] = None
    total: int
    results: List[AddressItem]


class IndexStats(BaseModel):
    """Статистика индекса"""
    total_documents: int
    index_size: str
    regions_count: int
    cities_count: int
    streets_count: int
    houses_count: int

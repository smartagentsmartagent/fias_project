"""
Сервис поиска в Elasticsearch
"""
import asyncio
from typing import List, Optional, Dict, Any
from elasticsearch import Elasticsearch
from config import settings
import logging

from .models import AddressItem, GeoPoint

logger = logging.getLogger(__name__)


class SearchService:
    """Сервис для поиска адресов в Elasticsearch"""
    
    def __init__(self, es_client: Elasticsearch, index_name: str):
        self.es = es_client
        self.index = index_name
    
    def _beautify_full_name(self, full_name: str) -> str:
        """Убирает повторяющееся начальное слово следующего сегмента,
        если оно уже встречалось в предыдущем сегменте (по словам).
        Пример: "... даниловский вн/тер-г, даниловский пер" -> "... даниловский вн/тер-г, пер".
        """
        if not full_name:
            return full_name
        parts = [p.strip() for p in full_name.split(',')]
        if len(parts) <= 1:
            return full_name.strip()
        # Набор типовых токенов уличных/админ типов, которые не должны оставаться в одиночку
        type_tokens = {
            "ул","пер","пр-кт","б-р","пр-д","пл","ш","наб","туп","ал","дор","тракт","мост","эст","п/п",
            "съезд","заезд","подъезд-авт","просека","просёлок","линия","ряд","кольцо","автодорога","трасса",
            # Админ/нормализованные вспомогательные
            "г","мо","р-н","вн/тер-г"
        }
        
        # Набор типов населённых пунктов, которые НЕ должны терять своё название
        settlement_types = {"рп", "п", "с", "д", "ст", "х", "кв-л", "мкр", "тер"}
        cleaned = []
        prev_non_type_words = set()
        for idx, part in enumerate(parts):
            words = [w for w in part.split() if w]
            original_words = list(words)
            if idx > 0 and words:
                first = words[0]
                # Не удаляем первый токен, если после удаления останется только тип (например, "пер")
                # ИЛИ если это населённый пункт с названием (например, "киевский рп")
                if first in prev_non_type_words:
                    if len(words) >= 2 and (words[1] in type_tokens or words[1] in settlement_types):
                        # Оставляем как есть: это, вероятно, имя+тип (напр. "даниловский пер") 
                        # или населённый пункт (напр. "киевский рп")
                        pass
                    else:
                        words = words[1:]
            cleaned_part = ' '.join(words).strip()
            # Страховка: если очистка привела к пустоте или к единственному типу, вернем исходный сегмент
            if not cleaned_part or cleaned_part in type_tokens:
                cleaned_part = ' '.join(original_words).strip()
            cleaned.append(cleaned_part)
            # Обновим множество значимых слов предыдущего сегмента (исключая типовые токены)
            prev_non_type_words = set([w for w in cleaned_part.split() if w and w not in type_tokens])
        return ', '.join([p for p in cleaned if p])
    
    async def search(
        self,
        query: str,
        house_number: Optional[str] = None,
        korpus: Optional[str] = None,
        stroenie: Optional[str] = None,
        limit: int = 10,
        full_phrase: Optional[str] = None,
        expanded_phrase: Optional[str] = None,
        has_moscow: bool = False,
        has_moscow_region: bool = False,
        has_balashikha: bool = False,
        has_leningrad_region: bool = False,
        original_query: Optional[str] = None
    ) -> List[AddressItem]:
        """Основной метод поиска"""
        try:
            # Выполняем поиск в отдельном потоке
            results = await asyncio.to_thread(
                self._search_sync,
                query,
                house_number,
                korpus,
                stroenie,
                limit,
                full_phrase,
                expanded_phrase,
                has_moscow,
                has_moscow_region,
                has_balashikha,
                has_leningrad_region,
                original_query,
            )
            return results
        except Exception as e:
            logger.error(f"Ошибка поиска: {e}")
            return []
    
    def _search_sync(
        self,
        query: str,
        house_number: Optional[str] = None,
        korpus: Optional[str] = None,
        stroenie: Optional[str] = None,
        limit: int = 10,
        full_phrase: Optional[str] = None,
        expanded_phrase: Optional[str] = None,
        has_moscow: bool = False,
        has_moscow_region: bool = False,
        has_balashikha: bool = False,
        has_leningrad_region: bool = False,
        original_query: Optional[str] = None
    ) -> List[AddressItem]:
        """Синхронный поиск"""
        if not query.strip():
            return []
        
        # Вспомогательная морф-упрощалка окончаний прилагательных/родительного падежа
        def generate_morph_variants(text: str) -> List[str]:
            if not text:
                return []
            tokens = [t for t in text.split() if t]
            variants: List[str] = []
            def norm_adj(tok: str) -> str:
                # Очень лёгкая нормализация. Не трогаем числовые/смешанные (остаются как есть)
                if any(ch.isdigit() for ch in tok):
                    return tok
                # типовые русские окончания прилагательных/род. падежа
                repls = [
                    ("ского", "ский"), ("сого", "сый"), ("его", "ий"), ("ого", "ий"),
                    ("ской", "ская"), ("цкой", "цкая"), ("ой", "ая"), ("ий", "ий"),
                    ("ая", "ая"), ("ое", "ое"), ("ые", "ый"), ("ых", "ый"), ("их", "ий")
                ]
                for src, dst in repls:
                    if tok.endswith(src):
                        return tok[: -len(src)] + dst
                return tok
            normed = [norm_adj(t) for t in tokens]
            if normed != tokens:
                variants.append(" ".join(normed))
            return variants

        # Перестановка типа улицы в конец сегмента (например: "пл савеловского вокзала" -> "савеловского вокзала пл")
        def move_street_type_to_tail(text: str) -> Optional[str]:
            if not text:
                return None
            tokens = [t for t in text.split() if t]
            if not tokens:
                return None
            street_type_tokens = {
                "ул", "пер", "пр-кт", "б-р", "пр-д", "пл", "ш", "наб", "туп",
                "ал", "дор", "тракт", "мост", "эст", "п/п", "линия", "ряд",
                "кольцо", "автодорога", "трасса"
            }
            try:
                idx = next(i for i, t in enumerate(tokens) if t in street_type_tokens)
            except StopIteration:
                return None
            # Не трогаем, если тип уже в конце
            if idx == len(tokens) - 1:
                return None
            new_tokens = tokens[:idx] + tokens[idx+1:] + [tokens[idx]]
            return " ".join(new_tokens)

        # Извлечение уличной фразы вида "ленина ул" или "комсомольский пр-кт" из текста запроса
        def extract_street_phrase(text: str) -> Optional[str]:
            street_types = {
                "ул", "пер", "пр-кт", "б-р", "пр-д", "пл", "ш", "наб", "туп",
                "ал", "дор", "тракт", "мост", "эст", "п/п", "линия", "ряд",
                "кольцо", "автодорога", "трасса"
            }
            tokens = [t for t in (text or "").split() if t]
            # Ищем последнее вхождение типа улицы
            type_idx = None
            for i in range(len(tokens)-1, -1, -1):
                if tokens[i] in street_types:
                    type_idx = i
                    break
            if type_idx is None:
                return None
            # Случай 1: тип стоит в конце — берём предыдущее слово (напр. "ленина ул")
            if type_idx >= 1:
                # Берем все слова после типа улицы до конца строки
                if type_idx < len(tokens) - 1:
                    name_part = " ".join(tokens[type_idx+1:])
                    return f"{name_part} {tokens[type_idx]}".strip()
                else:
                    return f"{tokens[type_idx-1]} {tokens[type_idx]}"
            # Случай 2: тип стоит в начале — формируем фразу "<имя> <тип>"
            # Пример: "ул юлиана семенова" -> "юлиана семенова ул"
            if type_idx == 0 and len(tokens) >= 2:
                name_part = " ".join(tokens[1:])
                return f"{name_part} {tokens[0]}".strip()
            return None
        
        # Генерация вариантов с заменой е/ё для лучшего поиска
        def generate_e_yo_variants(text: str) -> List[str]:
            if not text:
                return []
            variants = [text]
            # Заменяем е на ё
            if 'е' in text:
                variants.append(text.replace('е', 'ё'))
            # Заменяем ё на е
            if 'ё' in text:
                variants.append(text.replace('ё', 'е'))
            return variants

        # Базовый поисковый запрос
        search_body = {
            "size": limit,
            "query": {
                "bool": {
                    "must": [],
                    "should": [
                        # Очень высокий буст для точного совпадения названия улицы
                        {
                            "match_phrase": {
                                "name_norm": {
                                    "query": query,
                                    "boost": 20.0  # Увеличили с 4.0 до 20.0
                                }
                            }
                        },
                        # Высокий буст для точного совпадения названия улицы с fuzziness
                        {
                            "match": {
                                "name_norm": {
                                    "query": query,
                                    "boost": 10.0,  # Увеличили с 2.0 до 10.0
                                    "fuzziness": "AUTO"
                                }
                            }
                        },
                        # Дополнительный буст для точного совпадения в name_exact
                        {
                            "match_phrase": {
                                "name_exact": {
                                    "query": query,
                                    "boost": 25.0
                                }
                            }
                        },
                        # Фразовое совпадение по полю полного адреса с высоким бустом
                    ],
                    "minimum_should_match": 0
                }
            },
            "_source": [
                "level", "name_norm", "name_exact", "full_norm", 
                "type_norm", "region_code", "geo", "house_number",
                "korpus", "stroenie", "house_type", "road_km",
                "street_guid", "settlement_guid", "city_guid", "name_lem"
            ]
        }

        # Добавляем should-условия динамически
        dynamic_should: List[Dict[str, Any]] = []
        
        # Определяем токены запроса для использования в логике поиска
        query_tokens = [t for t in (query or "").split() if t]
        
        # Специальная логика для поиска улиц с типом в начале запроса
        # Например, "ул большая дмитровка" -> также ищем "большая дмитровка" и "дмитровка большая"
        if query_tokens and query_tokens[0] in {"ул", "пер", "пр-кт", "б-р", "пр-д", "пл", "ш", "наб", "туп", "ал", "дор", "тракт", "мост", "эст", "п/п", "линия", "ряд", "кольцо", "автодорога", "трасса"}:
            # Убираем тип улицы из начала запроса
            street_name_without_type = " ".join(query_tokens[1:])
            if street_name_without_type:
                # Ищем по названию без типа улицы
                dynamic_should.append({
                    "match_phrase": {
                        "name_norm": {
                            "query": street_name_without_type,
                            "boost": 15.0
                        }
                    }
                })
                dynamic_should.append({
                    "match_phrase": {
                        "full_norm": {
                            "query": street_name_without_type,
                            "boost": 12.0
                        }
                    }
                })
                
                # Также ищем с переставленными словами (например, "большая дмитровка" -> "дмитровка большая")
                street_tokens = street_name_without_type.split()
                if len(street_tokens) == 2:
                    # Переставляем два слова местами
                    reversed_name = f"{street_tokens[1]} {street_tokens[0]}"
                    dynamic_should.append({
                        "match_phrase": {
                            "name_norm": {
                                "query": reversed_name,
                                "boost": 18.0
                            }
                        }
                    })
                    dynamic_should.append({
                        "match_phrase": {
                            "full_norm": {
                                "query": reversed_name,
                                "boost": 15.0
                            }
                        }
                    })
                elif len(street_tokens) > 2:
                    # Для более чем 2 слов, переставляем первое и последнее
                    reversed_name = " ".join([street_tokens[-1]] + street_tokens[1:-1] + [street_tokens[0]])
                    dynamic_should.append({
                        "match_phrase": {
                            "name_norm": {
                                "query": reversed_name,
                                "boost": 16.0
                            }
                        }
                    })
                    dynamic_should.append({
                        "match_phrase": {
                            "full_norm": {
                                "query": reversed_name,
                                "boost": 13.0
                            }
                        }
                    })

        # Фразовое совпадение по полю полного адреса
        if full_phrase:
            dynamic_should.append({
                "match_phrase": {
                    "full_norm": {
                        "query": full_phrase,
                        "boost": 15.0  # Увеличили с 10.0 до 15.0
                    }
                }
            })
            # Дополнительно усилим фразу без дома как точную
            dynamic_should.append({
                "match_phrase": {
                    "full_norm": {
                        "query": query,
                        "boost": 12.0  # Увеличили с 6.0 до 12.0
                    }
                }
            })
            # Перестановка типа улицы в конец (если применимо) для full_phrase и query
            tail_variant_query = move_street_type_to_tail(query)
            if tail_variant_query:
                dynamic_should.append({
                    "match_phrase": {
                        "full_norm": {
                            "query": tail_variant_query,
                            "boost": 8.0
                        }
                    }
                })
                # Также фразовый матч по name_norm с перестановкой
                dynamic_should.append({
                    "match_phrase": {
                        "name_norm": {
                            "query": tail_variant_query,
                            "boost": 18.0
                        }
                    }
                })
            tail_variant_full = move_street_type_to_tail(full_phrase)
            if tail_variant_full:
                dynamic_should.append({
                    "match_phrase": {
                        "full_norm": {
                            "query": tail_variant_full,
                            "boost": 9.0
                        }
                    }
                })
            
            # Добавляем варианты с заменой е/ё для лучшего поиска
            e_yo_variants_query = generate_e_yo_variants(query)
            for variant in e_yo_variants_query:
                if variant != query:  # Не дублируем оригинальный запрос
                    dynamic_should.append({
                        "match_phrase": {
                            "full_norm": {
                                "query": variant,
                                "boost": 10.0
                            }
                        }
                    })
                    # Также добавляем перестановку типа для вариантов
                    tail_variant = move_street_type_to_tail(variant)
                    if tail_variant:
                        dynamic_should.append({
                            "match_phrase": {
                                "full_norm": {
                                    "query": tail_variant,
                                    "boost": 8.5
                                }
                            }
                        })
                        # И фразу по name_norm
                        dynamic_should.append({
                            "match_phrase": {
                                "name_norm": {
                                    "query": tail_variant,
                                    "boost": 15.0
                                }
                            }
                        })
        # В любом случае добавим неблокирующий match по full_norm на текст без дома,
        # чтобы не заваливаться из-за minimum_should_match
        dynamic_should.append({
            "match": {
                "full_norm": {
                    "query": query,
                    "operator": "and",
                    "boost": 1.5
                }
            }
        })

        # Fallback-логика для алиасов сокращений названий улиц
        # Если поиск не находит результаты, пробуем варианты с обратными алиасами
        alias_fallback_variants = []
        
        # Алиасы сокращений названий улиц
        street_aliases = {
            "большая": ["б", "б."],
            "малая": ["м", "м."],
            "средняя": ["ср", "ср.", "с"],
            "новая": ["н", "н."],
            "старая": ["ст", "ст."],
            "верхняя": ["в", "в."],
            "нижняя": ["ниж", "ниж."],
            "восточная": ["вост", "вост."],
            "западная": ["зап", "зап."],
            "северная": ["сев", "сев."],
            "южная": ["юж", "юж."],
            "центральная": ["центр", "центр."],
            "промышленная": ["пром", "пром."],
            "строительная": ["стр", "стр."],
            "железнодорожная": ["жд", "ж.д."],
            "красная": ["кр", "кр."],
            "советская": ["сов", "сов."],
            "комсомольская": ["комс", "комс."],
            "пионерская": ["пион", "пион."],
            "октябрьская": ["окт", "окт."],
            "молодежная": ["мол", "мол."],
            "школьная": ["шк", "шк."]
        }
        
        # Генерируем варианты с обратными алиасами
        query_tokens = query.split()
        for i, token in enumerate(query_tokens):
            for full_name, aliases in street_aliases.items():
                if token == full_name:
                    # Заменяем полное название на сокращения
                    for alias in aliases:
                        variant_tokens = query_tokens.copy()
                        variant_tokens[i] = alias
                        alias_fallback_variants.append(" ".join(variant_tokens))
                elif token in aliases:
                    # Заменяем сокращение на полное название
                    variant_tokens = query_tokens.copy()
                    variant_tokens[i] = full_name
                    alias_fallback_variants.append(" ".join(variant_tokens))
        
        # Добавляем варианты с алиасами в поиск
        for variant in alias_fallback_variants:
            if variant != query:  # Не дублируем оригинальный запрос
                dynamic_should.append({
                    "match_phrase": {
                        "name_norm": {
                            "query": variant,
                            "boost": 8.0
                        }
                    }
                })
                dynamic_should.append({
                    "match_phrase": {
                        "full_norm": {
                            "query": variant,
                            "boost": 6.0
                        }
                    }
                })
                # Также добавляем перестановку типа для вариантов с алиасами
                tail_variant = move_street_type_to_tail(variant)
                if tail_variant:
                    dynamic_should.append({
                        "match_phrase": {
                            "name_norm": {
                                "query": tail_variant,
                                "boost": 7.0
                            }
                        }
                    })
                    dynamic_should.append({
                        "match_phrase": {
                            "full_norm": {
                                "query": tail_variant,
                                "boost": 5.0
                            }
                        }
                    })
        
        # Дополнительная fallback-логика для поиска по частям названия улицы
        # Если точный поиск не работает, пробуем найти улицы, содержащие все слова из запроса
        if len(query_tokens) >= 2:
            # Ищем улицы, которые содержат все слова из запроса (в любом порядке)
            dynamic_should.append({
                "bool": {
                    "must": [
                        {"term": {"level": "street"}},
                        *[{"match": {"name_norm": {"query": token}}} for token in query_tokens if token not in {"ул", "пер", "пр-кт", "б-р", "пр-д", "пл", "ш", "наб", "туп", "ал", "дор", "тракт", "мост", "эст", "п/п", "линия", "ряд", "кольцо", "автодорога", "трасса"}]
                    ],
                    "boost": 3.0
                }
            })
            
            # Также пробуем поиск по full_norm с частями названия
            dynamic_should.append({
                "bool": {
                    "must": [
                        {"term": {"level": "street"}},
                        *[{"match": {"full_norm": {"query": token}}} for token in query_tokens if token not in {"ул", "пер", "пр-кт", "б-р", "пр-д", "пл", "ш", "наб", "туп", "ал", "дор", "тракт", "мост", "эст", "п/п", "линия", "ряд", "кольцо", "автодорога", "трасса"}]
                    ],
                    "boost": 2.0
                }
            })
            
            # Дополнительная логика для поиска улиц с алиасами в названии
            # Например, "ул большая дмитровка" -> ищем "дмитровка б."
            street_name_tokens = [token for token in query_tokens if token not in {"ул", "пер", "пр-кт", "б-р", "пр-д", "пл", "ш", "наб", "туп", "ал", "дор", "тракт", "мост", "эст", "п/п", "линия", "ряд", "кольцо", "автодорога", "трасса"}]
            if len(street_name_tokens) >= 2:
                # Ищем улицы, которые содержат все слова из названия улицы
                dynamic_should.append({
                    "bool": {
                        "must": [
                            {"term": {"level": "street"}},
                            *[{"match": {"name_norm": {"query": token}}} for token in street_name_tokens]
                        ],
                        "boost": 4.0
                    }
                })
                
                # Также пробуем поиск по full_norm с названием улицы
                dynamic_should.append({
                    "bool": {
                        "must": [
                            {"term": {"level": "street"}},
                            *[{"match": {"full_norm": {"query": token}}} for token in street_name_tokens]
                        ],
                        "boost": 3.0
                    }
                })
                
                # Специальная логика для поиска улиц с алиасами в названии
                # Например, "ул большая дмитровка" -> ищем "дмитровка б."
                # Проверяем, есть ли в названии улицы слова, которые могут быть алиасами
                alias_keywords = {"большая", "малая", "средняя", "новая", "старая", "верхняя", "нижняя", "восточная", "западная", "северная", "южная", "центральная", "промышленная", "строительная", "железнодорожная", "красная", "советская", "комсомольская", "пионерская", "октябрьская", "молодежная", "школьная"}
                for keyword in street_name_tokens:
                    if keyword in alias_keywords:
                        # Ищем улицы, которые содержат основное название улицы
                        main_street_tokens = [token for token in street_name_tokens if token != keyword]
                        if main_street_tokens:
                            dynamic_should.append({
                                "bool": {
                                    "must": [
                                        {"term": {"level": "street"}},
                                        *[{"match": {"name_norm": {"query": token}}} for token in main_street_tokens]
                                    ],
                                    "boost": 6.0
                                }
                            })
                            dynamic_should.append({
                                "bool": {
                                    "must": [
                                        {"term": {"level": "street"}},
                                        *[{"match": {"full_norm": {"query": token}}} for token in main_street_tokens]
                                    ],
                                    "boost": 5.0
                                }
                            })

        # Расширенная фраза с домом/корпусом/строением и допуском перестановок служебных слов
        if expanded_phrase:
            dynamic_should.append({
                "match_phrase": {
                    "full_norm": {
                        "query": expanded_phrase,
                        "slop": 4,
                        "boost": 9.0
                    }
                }
            })
            # Перестановка типа улицы в конец для expanded_phrase
            tail_variant_expanded = move_street_type_to_tail(expanded_phrase)
            if tail_variant_expanded:
                dynamic_should.append({
                    "match_phrase": {
                        "full_norm": {
                            "query": tail_variant_expanded,
                            "slop": 5,
                            "boost": 9.5
                        }
                    }
                })

        # Если запрос короткий и без номера дома — поднимем агрегирующие уровни
        query_tokens = [t for t in (query or "").split() if t]
        if not house_number and len(query_tokens) <= 2:
            # Явно поднимем города/внутригородские территории
            dynamic_should.append({
                "constant_score": {
                    "filter": {"term": {"level": "city"}},
                    "boost": 8.0
                }
            })
            # Очень сильный буст на точное совпадение названия для уровня city
            dynamic_should.append({
                "bool": {
                    "must": [
                        {"term": {"level": "city"}},
                        {"match_phrase": {"name_norm": {"query": query}}}
                    ],
                    "boost": 20.0
                }
            })
            # Небольшой буст для регионов
            dynamic_should.append({
                "constant_score": {
                    "filter": {"term": {"level": "region"}},
                    "boost": 2.0
                }
            })
            # Усилим тип вн/тер-г
            dynamic_should.append({
                "constant_score": {
                    "filter": {"term": {"type_norm": "вн/тер-г"}},
                    "boost": 3.0
                }
            })
        
        # Поддержка синонимов админ. единиц: район/р-н/вн/тер-г
        def replace_admin_token(q: str, to_token: str) -> str:
            tokens = q.split()
            admin_set = {"район", "р-н", "вн/тер-г", "м/о"}
            return " ".join([to_token if t in admin_set else t for t in tokens])

        admin_present = any(t in {"район", "р-н", "вн/тер-г", "м/о", "округ", "округа", "административный"} for t in query_tokens)

        if admin_present:
            # Варианты запроса с заменой на канон и на эквиваленты
            variant_tokens = ["район", "р-н", "вн/тер-г", "м/о"]
            query_variants = set()
            for vt in variant_tokens:
                query_variants.add(replace_admin_token(query, vt))
            # Сконструируем облегчённый must: удалим служебные админ-слова и потребуем совпадение по смысловым токенам
            admin_stopwords = {"район", "р-н", "вн/тер-г", "м/о", "округ", "округа", "административный", "г", "город", ","}
            def reduce_tokens(q: str) -> str:
                toks = [t for t in q.split() if t and t not in admin_stopwords]
                return " ".join(toks)
            mm_variants = []
            for qv in sorted(query_variants):
                reduced = reduce_tokens(qv)
                if reduced:
                    mm_variants.append({
                        "multi_match": {
                            "query": reduced,
                            "fields": ["name_norm^2", "full_norm"],
                            "type": "best_fields",
                            "operator": "and"
                        }
                    })
                    # Бэкап с более мягким оператором
                    mm_variants.append({
                        "multi_match": {
                            "query": reduced,
                            "fields": ["name_norm^2", "full_norm"],
                            "type": "best_fields",
                            "operator": "or",
                            "fuzziness": "AUTO"
                        }
                    })
                # Добавим фразовый матч по full_norm для каждого варианта
                dynamic_should.append({
                    "match_phrase": {"full_norm": {"query": qv, "boost": 5.0}}
                })
            if mm_variants:
                search_body["query"]["bool"]["must"].append({
                    "bool": {"should": mm_variants, "minimum_should_match": 1}
                })
            # Сильно поднимем админ-типы (район/м/о/вн/тер-г)
            admin_type_terms = ["р-н", "вн/тер-г", "вн.тер.г.", "м/о"]
            dynamic_should.append({
                "constant_score": {"filter": {"terms": {"type_norm": admin_type_terms}}, "boost": 300.0}
            })
            # Сильно приоритизируем городские документы с админ-типами
            dynamic_should.append({
                "bool": {
                    "must": [
                        {"term": {"level": "city"}},
                        {"terms": {"type_norm": admin_type_terms}}
                    ],
                    "boost": 400.0
                }
            })
            # Для коротких запросов без дома — ограничим выдачу только админ-типами
            # Если это административный запрос без номера дома — ограничим выдачу админ-типами
            if not house_number:
                existing_filters = search_body["query"]["bool"].get("filter", [])
                existing_filters.append({"terms": {"type_norm": admin_type_terms}})
                search_body["query"]["bool"]["filter"] = existing_filters
        
        # Приоритизация Москвы для длинных иерархий
        # Если в запросе есть "москва" или передана информация о наличии "москва", усилим результаты из Москвы
        if "москва" in query.lower() or has_moscow:
            # Буст для результатов из Москвы (по коду региона 77)
            dynamic_should.append({
                "constant_score": {
                    "filter": {"terms": {"region_code": ["77", 77]}},
                    "boost": 100.0
                }
            })
            
            # Дополнительный буст для вн/тер-г в Москве
            dynamic_should.append({
                "bool": {
                    "filter": [
                        {"terms": {"region_code": ["77", 77]}},
                        {"term": {"type_norm": "вн/тер-г"}}
                    ],
                    "boost": 50.0
                }
            })
            
            # Для длинных иерархий (административные округа) усилим точность
            if any(t in {"административный", "округа", "округ"} for t in query_tokens):
                dynamic_should.append({
                    "match_phrase": {
                        "full_norm": {
                            "query": query,
                            "boost": 50.0  # Увеличили буст
                        }
                    }
                })
            
            # Применяем СТРОГИЙ фильтр по региону для Москвы - только результаты из Москвы
            existing_filters = search_body["query"]["bool"].get("filter", [])
            # Удаляем любые существующие фильтры по region_code, чтобы избежать конфликтов
            existing_filters = [f for f in existing_filters if not (isinstance(f, dict) and ("terms" in f or "term" in f) and "region_code" in f.get("terms", f.get("term", {})))]
            existing_filters.append({"terms": {"region_code": ["77", 77]}})
            search_body["query"]["bool"]["filter"] = existing_filters
        
        # Приоритизация Московской области для Балашихи
        # Если в запросе есть "балашиха" или передана информация о наличии "балашиха", усилим результаты из Московской области
        elif has_balashikha or "балашиха" in query.lower():
            # Буст для результатов из Московской области (по коду региона 50)
            dynamic_should.append({
                "constant_score": {
                    "filter": {"terms": {"region_code": ["50", 50]}},
                    "boost": 100.0
                }
            })
            
            # Дополнительный буст для городов в Московской области
            dynamic_should.append({
                "bool": {
                    "filter": [
                        {"terms": {"region_code": ["50", 50]}},
                        {"term": {"level": "city"}}
                    ],
                    "boost": 50.0
                }
            })
            
            # Очень высокий буст для результатов, содержащих "балашиха" в full_norm
            dynamic_should.append({
                "match_phrase": {
                    "full_norm": {
                        "query": "балашиха",
                        "boost": 200.0
                    }
                }
            })
            
            # Дополнительный буст для улиц и микрорайонов в Балашихе
            dynamic_should.append({
                "bool": {
                    "must": [
                        {"match_phrase": {"full_norm": {"query": "балашиха"}}},
                        {"terms": {"level": ["street", "settlement"]}}
                    ],
                    "boost": 150.0
                }
            })
            
            # Приоритизация микрорайонов и улиц по ключевым словам из запроса
            # Если в запросе есть "1 мая", приоритизируем микрорайоны "1 мая мкр" выше улиц "1 мая"
            query_tokens = [t.lower() for t in query.split()]
            for token in query_tokens:
                if token in ["1", "мая", "май"]:
                    # Очень высокий буст для микрорайонов "1 мая мкр" в Балашихе
                    dynamic_should.append({
                        "bool": {
                            "must": [
                                {"match_phrase": {"full_norm": {"query": "балашиха"}}},
                                {"match_phrase": {"name_norm": {"query": "1 мая мкр"}}}
                            ],
                            "boost": 5000.0
                        }
                    })
                    # Высокий буст для микрорайонов "1 мая мкр" в любом месте
                    dynamic_should.append({
                        "bool": {
                            "must": [
                                {"match_phrase": {"name_norm": {"query": "1 мая мкр"}}},
                                {"term": {"level": "settlement"}}
                            ],
                            "boost": 4000.0
                        }
                    })
                    # Также ищем микрорайоны с переставленными словами "мкр 1 мая"
                    dynamic_should.append({
                        "bool": {
                            "must": [
                                {"match_phrase": {"name_norm": {"query": "мкр 1 мая"}}},
                                {"term": {"level": "settlement"}}
                            ],
                            "boost": 4000.0
                        }
                    })
                    # Очень низкий буст для улиц "1 мая" в Балашихе (только если нет микрорайона)
                    dynamic_should.append({
                        "bool": {
                            "must": [
                                {"match_phrase": {"full_norm": {"query": "балашиха"}}},
                                {"match_phrase": {"name_norm": {"query": "1 мая"}}},
                                {"term": {"level": "street"}}
                            ],
                            "boost": 10.0
                        }
                    })
                    # Минимальный буст для улиц "1 мая" в любом месте
                    dynamic_should.append({
                        "bool": {
                            "must": [
                                {"match_phrase": {"name_norm": {"query": "1 мая"}}},
                                {"term": {"level": "street"}}
                            ],
                            "boost": 5.0
                        }
                    })
                    break
            
            # Применяем мягкий фильтр по региону для приоритизации Московской области
            existing_filters = search_body["query"]["bool"].get("filter", [])
            existing_filters.append({"terms": {"region_code": ["50", 50]}})
            search_body["query"]["bool"]["filter"] = existing_filters
        
        # Приоритизация Ленинградской области
        # Если в запросе есть "ленинградская область" или передана информация о наличии "ленинградская область", усилим результаты из Ленинградской области
        elif has_leningrad_region:
            # Буст для результатов из Ленинградской области (по коду региона 47)
            dynamic_should.append({
                "constant_score": {
                    "filter": {"terms": {"region_code": ["47", 47]}},
                    "boost": 100.0
                }
            })
            
            # Дополнительный буст для городов в Ленинградской области
            dynamic_should.append({
                "bool": {
                    "filter": [
                        {"terms": {"region_code": ["47", 47]}},
                        {"term": {"level": "city"}}
                    ],
                    "boost": 50.0
                }
            })
            
            # Применяем СТРОГИЙ фильтр по региону для Ленинградской области - только результаты из Ленинградской области
            existing_filters = search_body["query"]["bool"].get("filter", [])
            # Удаляем любые существующие фильтры по region_code, чтобы избежать конфликтов
            existing_filters = [f for f in existing_filters if not (isinstance(f, dict) and ("terms" in f or "term" in f) and "region_code" in f.get("terms", f.get("term", {})))]
            existing_filters.append({"terms": {"region_code": ["47", 47]}})
            search_body["query"]["bool"]["filter"] = existing_filters
            
            # Специальная логика для иерархических адресов в Ленинградской области
            # Если запрос содержит иерархию (например, "токсовское гп токсово гп"), ищем по фразе
            if "гп" in query or "пос" in query or "г/" in query:
                # Добавляем высокий буст для фразового поиска по полному адресу
                dynamic_should.append({
                    "match_phrase": {
                        "full_norm": {
                            "query": query,
                            "boost": 50.0
                        }
                    }
                })
                # Также ищем по нормализованному названию
                dynamic_should.append({
                    "match_phrase": {
                        "name_norm": {
                            "query": query,
                            "boost": 40.0
                        }
                    }
                })
        else:
            # Базовый must если нет админ-синонимов
            # Добавляем альтернативу operator=or как бэкап внутри must
            search_body["query"]["bool"]["must"].append({
                "bool": {
                    "should": [
                        {
                            "multi_match": {
                                "query": query,
                                "fields": ["name_norm^2", "full_norm"],
                                "type": "best_fields",
                                "operator": "and"
                            }
                        },
                        {
                            "multi_match": {
                                "query": query,
                                "fields": ["name_norm^2", "full_norm"],
                                "type": "best_fields",
                                "operator": "or",
                                "fuzziness": "AUTO"
                            }
                        }
                    ],
                    "minimum_should_match": 1
                }
            })
        
        # Фильтры по дому/корпусу/строению
        must_filters: List[Dict[str, Any]] = []
        # Если указан дом/корпус/строение — ограничим уровень документом "house"
        if house_number or korpus or stroenie:
            must_filters.append({"term": {"level": "house"}})
        if house_number:
            # Допускаем точное совпадение и варианты вида N/* (например, 21/2) наравне
            must_filters.append({
                "bool": {
                    "should": [
                        {"term": {"house_number": house_number}},
                        {"wildcard": {"house_number": f"{house_number}/*"}}
                    ],
                    "minimum_should_match": 1
                }
            })

        def build_korpus_variants(k: str) -> List[str]:
            variants = [k]
            variants.append(f"к {k}")
            variants.append(f"к.{k}")
            variants.append(f"к{k}")
            variants.append(f"корп {k}")
            variants.append(f"корп. {k}")
            variants.append(f"корп.{k}")
            variants.append(f"корпус {k}")
            variants.append(f"кор. {k}")
            variants.append(f"кор.{k}")
            return variants

        def build_stroenie_variants(s: str) -> List[str]:
            variants = [s]
            variants.append(f"с {s}")
            variants.append(f"с.{s}")
            variants.append(f"стр {s}")
            variants.append(f"стр. {s}")
            variants.append(f"стр.{s}")
            variants.append(f"строение {s}")
            # Поддержка вариантов «владение»
            variants.append(f"вл {s}")
            variants.append(f"вл.{s}")
            variants.append(f"влад {s}")
            variants.append(f"влад. {s}")
            variants.append(f"влад.{s}")
            variants.append(f"владение {s}")
            # Дополнительные варианты для МКАД
            variants.append(f"влд {s}")
            variants.append(f"влд.{s}")
            return variants

        if korpus and stroenie:
            korpus_variants = build_korpus_variants(korpus)
            stroenie_variants = build_stroenie_variants(stroenie)

            combined_variants = []
            korpus_tokens = [f"к {korpus}", f"к.{korpus}", f"к{korpus}", f"корп {korpus}", f"корп. {korpus}", f"корп.{korpus}", f"корпус {korpus}", f"кор. {korpus}", f"кор.{korpus}"]
            stroenie_tokens = [
                f"стр {stroenie}", f"стр. {stroenie}", f"стр.{stroenie}", f"с {stroenie}", f"с.{stroenie}", f"строение {stroenie}",
                f"вл {stroenie}", f"вл.{stroenie}", f"влад {stroenie}", f"влад. {stroenie}", f"влад.{stroenie}", f"владение {stroenie}"
            ]
            for kv in korpus_tokens:
                for sv in stroenie_tokens:
                    combined_variants.append(f"{kv} {sv}")

            must_filters.append({
                "bool": {
                    "should": [
                        # Вариант, когда всё закодировано в поле korpus
                        {"terms": {"korpus": combined_variants}},
                        # Вариант, когда korpus и stroenie лежат по отдельным полям
                        {
                            "bool": {
                                "must": [
                                    {"bool": {"should": [{"terms": {"korpus": korpus_variants}}], "minimum_should_match": 1}},
                                    {"bool": {"should": [{"terms": {"stroenie": stroenie_variants}}], "minimum_should_match": 1}}
                                ]
                            }
                        }
                    ],
                    "minimum_should_match": 1
                }
            })
        elif korpus:
            korpus_variants = build_korpus_variants(korpus)
            must_filters.append({
                "bool": {
                    "should": [
                        {"terms": {"korpus": korpus_variants}}
                    ],
                    "minimum_should_match": 1
                }
            })
        elif stroenie:
            stroenie_variants = build_stroenie_variants(stroenie)
            # Разрешим хранение строения как в поле stroenie, так и в korpus (реальные ETL часто пишут "стр 5" в korpus)
            # Также добавляем варианты с префиксом "стр" для поля korpus
            stroenie_korpus_variants = [f"стр {stroenie}", f"стр.{stroenie}", f"стр {stroenie}"]
            must_filters.append({
                "bool": {
                    "should": [
                        {"terms": {"stroenie": stroenie_variants}},
                        {"terms": {"korpus": stroenie_variants}},
                        {"terms": {"korpus": stroenie_korpus_variants}}
                    ],
                    "minimum_should_match": 1
                }
            })

        if must_filters:
            # Не перезаписываем существующие фильтры (например, регион), а добавляем
            existing_filters = search_body["query"]["bool"].get("filter", [])
            existing_filters.append({"bool": {"must": must_filters}})
            search_body["query"]["bool"]["filter"] = existing_filters

        # Фильтрация по уличной части для всех запросов с уличной фразой
        street_phrase = extract_street_phrase(query)
        if street_phrase:
            # Обязательный фильтр по уличной части, чтобы не подтягивать чужие улицы
            existing_filters = search_body["query"]["bool"].get("filter", [])
            # Используем full_norm, и добавляем варианты е/ё, чтобы покрыть оба написания
            street_variants = [street_phrase]
            for v in generate_e_yo_variants(street_phrase):
                if v not in street_variants:
                    street_variants.append(v)
            
            # Добавляем варианты с обратным преобразованием типов улиц (для случаев, когда в базе полные названия)
            # Например: "пр-д" -> "проезд", "ул" -> "улица"
            type_mapping = {
                "пр-д": "проезд",
                "ул": "улица", 
                "пер": "переулок",
                "пр-кт": "проспект",
                "б-р": "бульвар",
                "пл": "площадь",
                "ш": "шоссе",
                "наб": "набережная"
            }
            for variant in street_variants[:]:  # Копируем список, чтобы не изменять его во время итерации
                for short_type, full_type in type_mapping.items():
                    if short_type in variant:
                        full_variant = variant.replace(short_type, full_type)
                        if full_variant not in street_variants:
                            street_variants.append(full_variant)
            # Требуем совпадение уличной фразы либо в full_norm, либо в name_norm
            # Используем must вместо should для более строгой фильтрации
            street_must_clauses = []
            for v in street_variants:
                street_must_clauses.append({
                    "bool": {
                        "should": [
                            {"match_phrase": {"full_norm": {"query": v}}},
                            {"match_phrase": {"name_norm": {"query": v}}}
                        ],
                        "minimum_should_match": 1
                    }
                })
            # Добавляем фильтр по уличной части как обязательное условие
            search_body["query"]["bool"]["must"].append({
                "bool": {
                    "should": street_must_clauses,
                    "minimum_should_match": 1
                }
            })
            search_body["query"]["bool"]["filter"] = existing_filters
            # Дополнительное should для повышения релевантности внутри той же улицы
            search_body["query"]["bool"]["should"].append({
                "bool": {
                    "must": [
                        {"term": {"level": "house"}},
                        {"match_phrase": {"name_norm": {"query": street_phrase}}}
                    ],
                    "boost": 80.0
                }
            })

        # Дополнительный should для точного совпадения комбинации дом+корпус+строение
        if house_number:
            combo_must: List[Dict[str, Any]] = [{"term": {"house_number": house_number}}]
            if korpus:
                # Поддержка вариантов записи корпуса
                combo_must.append({"terms": {"korpus": build_korpus_variants(korpus)}})
            if stroenie:
                # Поддержка вариантов записи строения
                combo_must.append({"terms": {"stroenie": build_stroenie_variants(stroenie)}})
            
            # Требуем также совпадение по уличной части запроса, чтобы исключить чужие улицы
            search_body["query"]["bool"]["should"].append({
                "bool": {
                    "must": combo_must + [{"match": {"full_norm": {"query": query, "operator": "and"}}}],
                    "boost": 50.0
                }
            })

            # Сильный приоритет для домов на той же уличной части (строгий фразовый матч по full_norm)
            search_body["query"]["bool"]["should"].append({
                "bool": {
                    "must": [
                        {"term": {"level": "house"}},
                        {"match": {"full_norm": {"query": query, "operator": "and"}}}
                    ],
                    "boost": 65.0
                }
            })
            
            # Очень высокий приоритет для точного совпадения дома БЕЗ строения/корпуса
            # если в запросе не указаны строение/корпус
            if not korpus and not stroenie:
                search_body["query"]["bool"]["should"].append({
                    "bool": {
                        "must": [
                            {"term": {"house_number": house_number}},
                            {"bool": {"must_not": [{"exists": {"field": "stroenie"}}]}},
                            {"bool": {"must_not": [{"exists": {"field": "korpus"}}]}},
                            {"match": {"full_norm": {"query": query, "operator": "and"}}}
                        ],
                        "boost": 100.0  # Очень высокий буст для точного совпадения
                    }
                })
            
            # Усиленная логика для точного совпадения дом+строение
            # Это особенно важно для случаев типа "84с2" где строение может быть в korpus
            if stroenie:
                # Вариант 1: точное совпадение дом + строение в korpus
                stroenie_korpus_variants = build_stroenie_variants(stroenie)
                search_body["query"]["bool"]["should"].append({
                    "bool": {
                        "must": [
                            {"term": {"house_number": house_number}},
                            {"terms": {"korpus": stroenie_korpus_variants}},
                            # Требуем совпадение по уличной части запроса, чтобы не подтягивать чужие улицы
                            {"match": {"full_norm": {"query": query, "operator": "and"}}}
                        ],
                        "boost": 60.0  # Высокий буст для точного совпадения
                    }
                })
                
                # Вариант 2: точное совпадение дом + строение в stroenie
                search_body["query"]["bool"]["should"].append({
                    "bool": {
                        "must": [
                            {"term": {"house_number": house_number}},
                            {"terms": {"stroenie": stroenie_korpus_variants}},
                            # Требуем совпадение по уличной части запроса
                            {"match": {"full_norm": {"query": query, "operator": "and"}}}
                        ],
                        "boost": 60.0
                    }
                })
                
                # Вариант 3: фразовое совпадение в full_norm для дом+строение
                house_stroenie_phrase = f"дом {house_number} стр {stroenie}"
                # Ограничим фразовый буст также совпадением по уличной части запроса
                search_body["query"]["bool"]["should"].append({
                    "bool": {
                        "must": [
                            {"match_phrase": {"full_norm": {"query": house_stroenie_phrase}}},
                            {"match": {"full_norm": {"query": query, "operator": "and"}}}
                        ],
                        "boost": 70.0
                    }
                })

        # Бусты по типам, если в запросе встречаются индикаторы
        tokens_lc = set([t.lower() for t in query_tokens])
        def boost_type(type_values: List[str], boost_val: float):
            dynamic_should.append({
                "constant_score": {
                    "filter": {"terms": {"type_norm": type_values}},
                    "boost": boost_val
                }
            })

        # Дополнительные бусты для сценариев с номером дома, когда точного номера может не быть
        if house_number:
            # 1) Предпочитать дома на той же уличной части запроса, даже если номер отличается
            dynamic_should.append({
                "bool": {
                    "must": [
                        {"term": {"level": "house"}},
                        {"match_phrase": {"full_norm": {"query": query}}}
                    ],
                    "boost": 35.0
                }
            })
            # 2) Повысить документы, где номер дома начинается с указанного и имеет дополнение через '/'
            #    Пример: запрос "21" — поднимаем "21/2", "21/1" и т.п.
            dynamic_should.append({
                "wildcard": {
                    "house_number": {
                        "value": f"{house_number}/*",
                        "boost": 30.0
                    }
                }
            })
            # 3) Поиск номеров домов, начинающихся с того же числа
            #    Пример: запрос "7/5" — поднимаем "7", "7/1", "7/2" и т.п.
            house_base = house_number.split('/')[0] if '/' in house_number else house_number
            if house_base != house_number:
                dynamic_should.append({
                    "wildcard": {
                        "house_number": {
                            "value": f"{house_base}*",
                            "boost": 25.0
                        }
                    }
                })
                # Также ищем точное совпадение базового номера
                dynamic_should.append({
                    "term": {
                        "house_number": {
                            "value": house_base,
                            "boost": 20.0
                        }
                    }
                })
            # 3) Усилить фразовый матч всей фразы (с админ-иерархией), чтобы предпочесть нужную территорию
            if full_phrase:
                dynamic_should.append({
                    "match_phrase": {
                        "full_norm": {
                            "query": full_phrase,
                            "boost": 40.0
                        }
                    }
                })
        # площадь/вокзал - усиленный буст
        if ("пл" in tokens_lc) or any("вокзал" in t for t in tokens_lc):
            boost_type(["пл"], 35.0)  # Увеличили с 25.0 до 35.0
            # Дополнительный буст для точного совпадения названия площади
            dynamic_should.append({
                "bool": {
                    "must": [
                        {"term": {"type_norm": "пл"}},
                        {"match_phrase": {"name_norm": {"query": query, "boost": 40.0}}}
                    ],
                    "boost": 50.0  # Увеличили с 40.0 до 50.0
                }
            })
            # Дополнительный буст для точного совпадения названия площади
            dynamic_should.append({
                "match_phrase": {
                    "name_norm": {
                        "query": query,
                        "boost": 45.0
                    }
                }
            })
        # шоссе — отдельный сильный буст (ш)
        if ("ш" in tokens_lc) or ("ш." in tokens_lc):
            boost_type(["ш"], 35.0)  # Увеличили с 20.0 до 35.0
            dynamic_should.append({
                "bool": {
                    "must": [
                        {"term": {"type_norm": "ш"}},
                        {"match_phrase": {"name_norm": {"query": query, "boost": 25.0}}}
                    ],
                    "boost": 45.0  # Увеличили с 30.0 до 45.0
                }
            })
            # Дополнительный буст для точного совпадения названия шоссе
            dynamic_should.append({
                "match_phrase": {
                    "name_norm": {
                        "query": query,
                        "boost": 40.0
                    }
                }
            })
        # СНТ/садоводства
        if "снт" in tokens_lc:
            boost_type(["снт", "тер"], 12.0)
        # проспекты - усиленный буст
        if "пр" in tokens_lc or "пр-кт" in tokens_lc:
            boost_type(["пр-кт"], 20.0)
            # Дополнительный буст для точного совпадения названия проспекта
            dynamic_should.append({
                "bool": {
                    "must": [
                        {"term": {"type_norm": "пр-кт"}},
                        {"match_phrase": {"name_norm": {"query": query, "boost": 25.0}}}
                    ],
                    "boost": 35.0
                }
            })
        # посёлки — увеличим буст
        if "пос" in tokens_lc or "пос." in tokens_lc:
            boost_type(["пос"], 25.0)  # Увеличили с 15.0 до 25.0
            # Дополнительный буст для точного совпадения названия посёлка
            dynamic_should.append({
                "bool": {
                    "must": [
                        {"term": {"type_norm": "пос"}},
                        {"match_phrase": {"name_norm": {"query": query, "boost": 30.0}}}
                    ],
                    "boost": 40.0
                }
            })
            # Дополнительный буст для точного совпадения названия посёлка
            dynamic_should.append({
                "match_phrase": {
                    "name_norm": {
                        "query": query,
                        "boost": 35.0
                    }
                }
            })
        # рп
        if "рп" in tokens_lc:
            boost_type(["рп"], 6.0)
        # деревня/село — осторожный буст
        if "д" in tokens_lc:
            boost_type(["д"], 3.0)
        if "с" in tokens_lc:
            boost_type(["с"], 3.0)
        # Москва — усилим документы с кодом региона 77
        if "москва" in tokens_lc:
            dynamic_should.append({
                "constant_score": {
                    "filter": {"term": {"region_code": "77"}},
                    "boost": 50.0
                }
            })

        # МКАД — отдельно усилим совпадение по названию
        if any(t in {"мкад", "кад"} for t in tokens_lc):
            dynamic_should.append({
                "match_phrase": {"name_norm": {"query": "мкад", "boost": 20.0}}
            })
            
            # Если есть "вл" в запросе, добавим фильтр по типу владения
            if any("вл" in t.lower() for t in tokens_lc):
                # Ищем владения в МКАД
                dynamic_should.append({
                    "bool": {
                        "must": [
                            {"match_phrase": {"name_norm": {"query": "мкад"}}},
                            {"term": {"house_type": "владение"}}
                        ],
                        "boost": 30.0
                    }
                })
            
        # Поддержка новых полей индекса: house_type и road_km
        # house_type: владение/строение/сооружение/литера
        if stroenie:
            # Если есть строение, усилим совпадение с house_type="строение"
            dynamic_should.append({
                "constant_score": {
                    "filter": {"term": {"house_type": "строение"}},
                    "boost": 15.0  # Увеличили с 5.0 до 15.0
                }
            })
            # Дополнительный буст для точного совпадения строения
            dynamic_should.append({
                "match_phrase": {
                    "full_norm": {
                        "query": f"стр {stroenie}",
                        "boost": 25.0
                    }
                }
            })
            # Буст для варианта "с{stroenie}"
            dynamic_should.append({
                "match_phrase": {
                    "full_norm": {
                        "query": f"с{stroenie}",
                        "boost": 30.0
                    }
                }
            })
            
        # road_km для МКАД/КАД
        if any(t in {"мкад", "кад"} for t in tokens_lc):
            # Ищем километр в запросе
            import re
            km_match = re.search(r'(\d+)[-\s]*й?\s*километр', query.lower())
            if km_match:
                km_number = int(km_match.group(1))
                dynamic_should.append({
                    "constant_score": {
                        "filter": {"term": {"road_km": km_number}},
                        "boost": 20.0
                    }
                })
            
            # Усилим поиск по МКАД даже без road_km
            dynamic_should.append({
                "match_phrase": {
                    "full_norm": {
                        "query": "мкад",
                        "boost": 15.0
                    }
                }
            })
            
            # Если есть "вл" в запросе, усилим поиск владений
            if any("вл" in t.lower() for t in tokens_lc):
                dynamic_should.append({
                    "constant_score": {
                        "filter": {"term": {"house_type": "владение"}},
                        "boost": 10.0
                    }
                })

        # Применяем динамические should условия
        search_body["query"]["bool"]["should"].extend(dynamic_should)

        # Лёгкие морф-варианты запроса (например, "савеловского" -> "савеловский")
        morph_variants = generate_morph_variants(query)
        for mv in morph_variants:
            search_body["query"]["bool"]["should"].append({
                "multi_match": {
                    "query": mv,
                    "fields": ["name_norm", "full_norm"],
                    "type": "best_fields",
                    "operator": "and",
                    "boost": 1.4
                }
            })
            search_body["query"]["bool"]["should"].append({
                "match_phrase": {"full_norm": {"query": mv, "boost": 2.0}}
            })
        
        try:
            def exec_search(body: Dict[str, Any]):
                try:
                    import json as _json
                    logger.info(f"ES query: {_json.dumps(body, ensure_ascii=False)[:2000]}")
                except Exception:
                    pass
                return self.es.search(index=self.index, body=body, request_timeout=settings.ES_TIMEOUT)

            response = exec_search(search_body)
            hits = response.get("hits", {}).get("hits", [])

            # Fallback: если фильтры по дому дают 0 — постепенно ослабляем ТОЛЬКО домовые детали, не отпуская уровень
            if not hits:
                had_house = bool(house_number)
                had_korpus = bool(korpus)
                had_stroenie = bool(stroenie)

                def rebuild_filter(include_house: bool, include_k: bool, include_s: bool) -> List[Dict[str, Any]]:
                    musts: List[Dict[str, Any]] = []
                    # Всегда удерживаем уровень домов, если в исходном запросе были домовые компоненты
                    if had_house or had_korpus or had_stroenie:
                        musts.append({"term": {"level": "house"}})
                    if include_house and house_number:
                        musts.append({
                            "bool": {
                                "should": [
                                    {"term": {"house_number": house_number}},
                                    {"wildcard": {"house_number": f"{house_number}/*"}}
                                ],
                                "minimum_should_match": 1
                            }
                        })
                    if include_k and korpus:
                        korpus_variants = build_korpus_variants(korpus)
                        musts.append({
                            "bool": {
                                "should": [
                                    {"terms": {"korpus": korpus_variants}},
                                    # Допуск: некоторые ETL кладут значения строения в поле korpus
                                    {"terms": {"korpus": build_stroenie_variants(korpus)}}
                                ],
                                "minimum_should_match": 1
                            }
                        })
                    if include_s and stroenie:
                        stroenie_variants = build_stroenie_variants(stroenie)
                        musts.append({
                            "bool": {
                                "should": [
                                    {"terms": {"stroenie": stroenie_variants}},
                                    # Допуск: некоторые ETL кладут значения строения в поле korpus
                                    {"terms": {"korpus": stroenie_variants}}
                                ],
                                "minimum_should_match": 1
                            }
                        })
                    return musts

                def with_new_filter(body: Dict[str, Any], include_house: bool, include_k: bool, include_s: bool) -> Dict[str, Any]:
                    new_body = dict(body)
                    qb = dict(new_body["query"]["bool"])  # shallow copy
                    # Сохраним региональные/прочие фильтры, если были (например, region_code=77)
                    preserved_filters = []
                    for f in qb.get("filter", []) or []:
                        # Сохраняем любые filters кроме вложенных bool must по домам
                        if isinstance(f, dict) and ("terms" in f or "term" in f):
                            preserved_filters.append(f)
                    # Новый bool must по домам
                    house_filter = {"bool": {"must": rebuild_filter(include_house, include_k, include_s)}}
                    qb["filter"] = preserved_filters + [house_filter]
                    new_body["query"]["bool"] = qb
                    return new_body

                # Порядок: убрать stroenie -> убрать korpus -> убрать house_number
                attempt_bodies = []
                if had_stroenie:
                    attempt_bodies.append(with_new_filter(search_body, include_house=True, include_k=True, include_s=False))
                if had_korpus:
                    attempt_bodies.append(with_new_filter(search_body, include_house=True, include_k=False, include_s=True))
                if had_house:
                    attempt_bodies.append(with_new_filter(search_body, include_house=False, include_k=True, include_s=True))
                # Полностью без домовых фильтров, но оставим level=house
                attempt_bodies.append(with_new_filter(search_body, include_house=False, include_k=False, include_s=False))

                for b in attempt_bodies:
                    # Гарантируем, что уровень остаётся house, если вход содержал домовые компоненты
                    if house_number or korpus or stroenie:
                        qb = b.get("query", {}).get("bool", {})
                        filters = qb.get("filter", [])
                        # Добавим/сохраним term level=house
                        level_filter = {"term": {"level": "house"}}
                        if not any(isinstance(f, dict) and f.get("term", {}).get("level") == "house" for f in filters):
                            filters.append(level_filter)
                            qb["filter"] = filters
                            b["query"]["bool"] = qb
                    response = exec_search(b)
                    hits = response.get("hits", {}).get("hits", [])
                    if hits:
                        break

                # Попробуем чисто фильтрами по домам (без текстового must), если всё ещё пусто
                if not hits and (had_house or had_korpus or had_stroenie):
                    # Фильтровочный запрос, но сохраним регион и усилим улицу, если можем
                    filter_only_filters = [{"bool": {"must": rebuild_filter(include_house=had_house, include_k=had_korpus, include_s=had_stroenie)}}]
                    # Сохраним региональные фильтры из исходного запроса
                    for f in search_body.get("query", {}).get("bool", {}).get("filter", []) or []:
                        if isinstance(f, dict) and ("terms" in f or "term" in f):
                            filter_only_filters.append(f)
                    
                    # Добавим поиск похожих номеров домов
                    similar_house_filters = []
                    if house_number:
                        # Ищем номера домов, начинающиеся с того же числа
                        house_base = house_number.split('/')[0] if '/' in house_number else house_number
                        similar_house_filters.append({
                            "bool": {
                                "should": [
                                    {"wildcard": {"house_number": f"{house_base}*"}},
                                    {"wildcard": {"house_number": f"*{house_base}*"}}
                                ],
                                "minimum_should_match": 1
                            }
                        })
                    
                    filter_only_body: Dict[str, Any] = {
                        "size": limit,
                        "query": {
                            "bool": {
                                "filter": filter_only_filters + similar_house_filters,
                                # Небольшой must по уличной части, чтобы придерживаться исходной улицы
                                "must": [{"match": {"full_norm": {"query": query, "operator": "and"}}}]
                            }
                        },
                        "_source": search_body.get("_source", [])
                    }
                    response = exec_search(filter_only_body)
                    hits = response.get("hits", {}).get("hits", [])

            
                    # Финальный фолбэк: если всё ещё пусто — возвращаемся к общему поиску без домовых ограничений
            if not hits:
                # Проверяем, есть ли в запросе конкретная улица
                has_specific_street = False
                # Проверяем нормализованный query (где типы уже приведены к канону)
                if query and len(query.split()) >= 2:
                    # Если в нормализованном запросе есть тип улицы, значит была конкретная улица
                    street_types = {
                        "ул", "пер", "пр-кт", "б-р", "пр-д", "пл", "ш", "наб", "туп", "ал", "дор", "тракт", "мост", "эст", "п/п", "съезд", "заезд", "подъезд-авт", "просека", "просёлок", "линия", "ряд", "кольцо", "автодорога", "трасса"
                    }
                    query_tokens = [t for t in query.split() if t]
                    for token in query_tokens:
                        if token in street_types:
                            has_specific_street = True
                            break
                
                # Если есть конкретная улица, но точного совпадения нет — ищем похожие адреса
                if has_specific_street:
                    # Ищем похожие номера домов на той же улице
                    similar_house_body = {
                        "size": limit,
                        "query": {
                            "bool": {
                                "must": [
                                    {"match": {"full_norm": {"query": query, "operator": "and"}}},
                                    {"term": {"level": "house"}}
                                ],
                                "should": [],
                                "filter": []
                            }
                        },
                        "_source": search_body.get("_source", [])
                    }
                    
                    # Добавляем региональные фильтры, если они были в исходном запросе
                    region_code = None
                    if has_moscow:
                        region_code = "77"
                    elif has_moscow_region or has_balashikha:
                        region_code = "50"  # Московская область
                    elif has_leningrad_region:
                        region_code = "47"  # Ленинградская область
                    
                    if region_code:
                        similar_house_body["query"]["bool"]["filter"].append(
                            {"terms": {"region_code": [region_code, int(region_code)]}}
                        )
                    
                    # Если был номер дома, добавляем бусты для похожих номеров
                    if house_number:
                        # Буст для номеров, начинающихся с того же числа
                        house_base = house_number.split('/')[0] if '/' in house_number else house_number
                        similar_house_body["query"]["bool"]["should"].extend([
                            {"wildcard": {"house_number": f"{house_base}*"}},
                            {"wildcard": {"house_number": f"*{house_base}*"}}
                        ])
                    
                    # Если был корпус, добавляем буст для домов с корпусами
                    if korpus:
                        similar_house_body["query"]["bool"]["should"].append(
                            {"exists": {"field": "korpus"}, "boost": 2.0}
                        )
                    
                    # Если было строение, добавляем буст для домов со строениями
                    if stroenie:
                        similar_house_body["query"]["bool"]["should"].append(
                            {"exists": {"field": "stroenie"}, "boost": 2.0}
                        )
                    
                    response = exec_search(similar_house_body)
                    hits = response.get("hits", {}).get("hits", [])
                else:
                    # Только для общих запросов (без конкретной улицы) делаем fallback
                    def clone_body_wo_house(body: Dict[str, Any]) -> Dict[str, Any]:
                        nb = dict(body)
                        qb = dict(nb.get("query", {}).get("bool", {}))
                        # Сносим фильтры полностью
                        qb.pop("filter", None)
                        # Убираем must-блоки, если они излишне строгие, оставим как есть основной must
                        nb.setdefault("query", {})["bool"] = qb
                        return nb

                    region_code = None
                    if has_moscow:
                        region_code = "77"
                    elif has_moscow_region or has_balashikha:
                        region_code = "50"  # Московская область
                    elif has_leningrad_region:
                        region_code = "47"  # Ленинградская область
                    else:
                        # Fallback на старую логику
                        ql = (query or "").lower()
                        if "екатеринбург" in ql or "свердлов" in ql:
                            region_code = "66"

                    final_body = clone_body_wo_house(search_body)
                    # Добавим фильтр по региону, если распознали
                    if region_code:
                        qb = final_body["query"]["bool"]
                        filters = qb.get("filter", []) or []
                        # Поддержим числовой и строковый вариант
                        filters.append({"terms": {"region_code": [region_code, int(region_code)]}})
                        qb["filter"] = filters
                    # Усилим should для улиц/площадей, чтобы вернуть что-то осмысленное
                    final_body["query"]["bool"]["should"].extend([
                        {"constant_score": {"filter": {"term": {"level": "street"}}, "boost": 5.0}},
                        {"constant_score": {"filter": {"term": {"level": "city"}}, "boost": 2.0}},
                    ])
                    response = exec_search(final_body)
                    hits = response.get("hits", {}).get("hits", [])
            
            results = []
            for hit in hits:
                source = hit["_source"]
                score = hit.get("_score", 0.0)
                
                # Создаем объект адреса
                address = AddressItem(
                    id=hit["_id"],
                    level=source.get("level", "unknown"),
                    name=source.get("name_exact", source.get("name_norm", "")),
                    full_name=self._beautify_full_name(source.get("full_norm", "")),
                    region_code=str(source.get("region_code")) if source.get("region_code") else None,
                    score=score,
                    # Добавляем нормализованные поля
                    name_norm=source.get("name_norm"),
                    name_exact=source.get("name_exact"),
                    full_norm=source.get("full_norm"),
                    type_norm=source.get("type_norm"),
                    name_lem=source.get("name_lem")
                )
                
                # Добавляем координаты если есть
                if "geo" in source and source["geo"]:
                    geo_data = source["geo"]
                    if isinstance(geo_data, dict) and "lat" in geo_data and "lon" in geo_data:
                        address.geo = GeoPoint(
                            lat=float(geo_data["lat"]),
                            lon=float(geo_data["lon"])
                        )
                
                # Добавляем информацию о доме если есть
                if source.get("house_number"):
                    address.house_number = str(source["house_number"])
                    address.korpus = source.get("korpus")
                    address.stroenie = source.get("stroenie")
                
                # Добавляем новые поля из расширенного индекса
                address.house_type = source.get("house_type")
                address.road_km = source.get("road_km")
                address.street_guid = source.get("street_guid")
                address.settlement_guid = source.get("settlement_guid")
                address.city_guid = source.get("city_guid")
                
                results.append(address)
            
            return results
            
        except Exception as e:
            logger.error(f"Ошибка выполнения поиска в ES: {e}")
            return []
    
    async def get_index_stats(self) -> Dict[str, Any]:
        """Получение статистики индекса"""
        try:
            stats = await asyncio.to_thread(self._get_index_stats_sync)
            return stats
        except Exception as e:
            logger.error(f"Ошибка получения статистики: {e}")
            return {}
    
    def _get_index_stats_sync(self) -> Dict[str, Any]:
        """Синхронное получение статистики"""
        try:
            # Общая статистика индекса
            index_stats = self.es.indices.stats(index=self.index)
            total_docs = index_stats["indices"][self.index]["total"]["docs"]["count"]
            index_size = index_stats["indices"][self.index]["total"]["store"]["size_in_bytes"]
            
            # Подсчет по уровням
            aggs_query = {
                "size": 0,
                "aggs": {
                    "levels": {
                        "terms": {
                            "field": "level",
                            "size": 10
                        }
                    }
                }
            }
            
            response = self.es.search(index=self.index, body=aggs_query)
            level_counts = {}
            
            for bucket in response["aggregations"]["levels"]["buckets"]:
                level_counts[bucket["key"]] = bucket["doc_count"]
            
            return {
                "total_documents": total_docs,
                "index_size_bytes": index_size,
                "level_counts": level_counts
            }
            
        except Exception as e:
            logger.error(f"Ошибка получения статистики из ES: {e}")
            return {}

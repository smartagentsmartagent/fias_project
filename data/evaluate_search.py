"""
Оценка качества поиска по списку запросов.

Формат входного CSV (UTF-8, с заголовком):
  - query: строка запроса
  - expected_full_substr (опц.): подстрока, которая должна встретиться в full_name найденного результата
  - expected_house_number (опц.)
  - expected_korpus (опц.)
  - expected_stroenie (опц.)
  - must_be_top1 (опц.): true/false — если true, учитываем успех только если ожидаемый попал на позицию 1

Метрики:
  - found_any: доля запросов с любой выдачей
  - match@1, match@3, match@5: доля запросов, где ожидаемый результат найден в топ-1/3/5
  - MRR@10: средняя reciprocal rank ожидаемого результата в топ-10
  - pos_hist: распределение позиции первого совпадения (1..10, либо >10/не найдено)
"""
import argparse
import csv
import json
import sys
import os
import time
from dataclasses import dataclass
from typing import List, Optional, Dict, Any, Tuple

import requests


PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
sys.path.append(PROJECT_ROOT)

try:
    from config import settings  # type: ignore
except Exception:
    class Dummy:
        ES_HOST = 'localhost'
    settings = Dummy()


@dataclass
class QueryCase:
    query: str
    expected_full_substr: Optional[str] = None
    expected_house_number: Optional[str] = None
    expected_korpus: Optional[str] = None
    expected_stroenie: Optional[str] = None
    must_be_top1: bool = False


def normalize_token(value: Optional[str]) -> Optional[str]:
    if value is None:
        return None
    v = str(value).strip().lower()
    if v == "":
        return None
    return v


def normalize_korpus_or_stroenie(raw: Optional[str]) -> Optional[str]:
    """Нормализует корпус/строение к компактной форме без префиксов.
    Примеры:
      "4" -> "4"
      "к 4" -> "4"
      "корп 4" -> "4"
      "корпус 4" -> "4"
      "к4" -> "4"
      "к 4 стр 1" -> "4" (строение отдельно вернётся из другой колонки)
    """
    v = normalize_token(raw)
    if v is None:
        return None
    replacements = [
        ("корпус", " "),
        ("корп", " "),
        ("к ", ""),
        ("к", ""),
        ("строение", " "),
        ("стр ", ""),
        ("стр", ""),
        ("с ", ""),
        ("с", ""),
    ]
    for src, dst in replacements:
        v = v.replace(src, dst)
    v = " ".join(v.split())
    # Берём первое "слово" как основное значение корпуса/строения
    if not v:
        return None
    return v.split()[0]


def is_expected_match(item: Dict[str, Any], case: QueryCase) -> bool:
    # Если задана подстрока — проверяем сначала её
    if case.expected_full_substr:
        full = str(item.get('full_name') or "").lower()
        if case.expected_full_substr.lower() not in full:
            return False

    # Поля дома/корпуса/строения, если заданы — сверяем
    if case.expected_house_number:
        if str(item.get('house_number') or "").lower() != case.expected_house_number.lower():
            return False

    if case.expected_korpus:
        korpus_item = normalize_korpus_or_stroenie(item.get('korpus'))
        if korpus_item is None or korpus_item != case.expected_korpus.lower():
            return False

    if case.expected_stroenie:
        stroenie_item = normalize_korpus_or_stroenie(item.get('stroenie'))
        if stroenie_item is None or stroenie_item != case.expected_stroenie.lower():
            return False

    return True


def fetch_results(api_url: str, query: str, limit: int) -> Dict[str, Any]:
    resp = requests.get(api_url.rstrip('/') + '/search', params={'q': query, 'limit': limit}, timeout=20)
    resp.raise_for_status()
    return resp.json()


def evaluate(cases: List[QueryCase], api_url: str, limit: int = 10) -> Dict[str, Any]:
    total = len(cases)
    found_any = 0
    match_at_1 = 0
    match_at_3 = 0
    match_at_5 = 0
    mrr_total = 0.0
    pos_hist: Dict[str, int] = {str(i): 0 for i in range(1, 11)}
    pos_hist[">10"] = 0
    pos_hist["not_found"] = 0

    per_case: List[Dict[str, Any]] = []

    for idx, case in enumerate(cases, 1):
        try:
            data = fetch_results(api_url, case.query, limit)
            results = data.get('results', [])
            if results:
                found_any += 1

            # Найдём первую позицию совпадения по ожиданиям
            first_pos = None
            for i, item in enumerate(results, start=1):
                if is_expected_match(item, case):
                    first_pos = i
                    break

            if first_pos is None:
                pos_hist["not_found"] += 1
            else:
                if first_pos <= 10:
                    pos_hist[str(first_pos)] += 1
                else:
                    pos_hist[">10"] += 1

                if first_pos == 1:
                    match_at_1 += 1
                if first_pos <= 3:
                    match_at_3 += 1
                if first_pos <= 5:
                    match_at_5 += 1
                mrr_total += 1.0 / float(first_pos)

            success = False
            if case.must_be_top1:
                success = (first_pos == 1)
            else:
                success = (first_pos is not None)

            per_case.append({
                'query': case.query,
                'first_pos': first_pos,
                'total': len(results),
                'success': success
            })
        except Exception as e:
            per_case.append({
                'query': case.query,
                'error': str(e)
            })

    summary = {
        'total': total,
        'found_any': found_any,
        'found_any_pct': round(100.0 * found_any / total, 2) if total else 0.0,
        'match@1': match_at_1,
        'match@1_pct': round(100.0 * match_at_1 / total, 2) if total else 0.0,
        'match@3': match_at_3,
        'match@3_pct': round(100.0 * match_at_3 / total, 2) if total else 0.0,
        'match@5': match_at_5,
        'match@5_pct': round(100.0 * match_at_5 / total, 2) if total else 0.0,
        'mrr@10': round(mrr_total / total, 4) if total else 0.0,
        'pos_hist': pos_hist,
    }

    return {
        'summary': summary,
        'details': per_case
    }


def load_cases_from_csv(path: str) -> List[QueryCase]:
    cases: List[QueryCase] = []
    with open(path, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            cases.append(QueryCase(
                query=row.get('query', '').strip(),
                expected_full_substr=(row.get('expected_full_substr') or '').strip() or None,
                expected_house_number=(row.get('expected_house_number') or '').strip() or None,
                expected_korpus=(row.get('expected_korpus') or '').strip() or None,
                expected_stroenie=(row.get('expected_stroenie') or '').strip() or None,
                must_be_top1=str(row.get('must_be_top1') or '').strip().lower() in ('1', 'true', 'yes')
            ))
    return cases


def main():
    parser = argparse.ArgumentParser(description='Оценка качества поиска по списку запросов')
    parser.add_argument('--api-url', default='http://147.45.214.115:8000', help='Базовый URL API')
    parser.add_argument('--input', required=True, help='Путь к CSV с кейсами')
    parser.add_argument('--limit', type=int, default=10, help='Лимит результатов на запрос')
    parser.add_argument('--out-json', default='', help='Сохранить отчёт в JSON')
    args = parser.parse_args()

    cases = load_cases_from_csv(args.input)
    if not cases:
        print('Нет кейсов для проверки', file=sys.stderr)
        sys.exit(2)

    started = time.time()
    report = evaluate(cases, api_url=args.api_url, limit=args.limit)
    elapsed = time.time() - started

    print('Итоги:')
    print(json.dumps(report['summary'], ensure_ascii=False, indent=2))
    print(f'Время: {elapsed:.2f} c, кейсов: {len(cases)}')

    if args.out_json:
        with open(args.out_json, 'w', encoding='utf-8') as f:
            json.dump(report, f, ensure_ascii=False, indent=2)
        print(f'Отчёт сохранён: {args.out_json}')


if __name__ == '__main__':
    main()




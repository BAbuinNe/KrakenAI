"""Transparent, conservative ranking for supplier proposals.

Ranking cannot override an explicit failed or unknown mandatory requirement.
Scores are preliminary heuristics, not a vendor reliability guarantee.
"""
from __future__ import annotations
import math
from typing import Any

DEFAULT_WEIGHTS = {'compliance': 60.0, 'price': 25.0, 'delivery': 15.0, 'reliability': 0.0}
LABELS = {'compliance': 'Соответствие ТЗ', 'price': 'Цена', 'delivery': 'Срок поставки',
          'reliability': 'Надёжность (ручная оценка)'}

def clean_inputs(weights: dict[str, float] | None = None,
                 reliability: dict[str, float] | None = None,
                 supplier_names: set[str] | None = None) -> tuple[dict[str, float], dict[str, float]]:
    values = dict(DEFAULT_WEIGHTS) if weights is None else dict(weights)
    if set(values) != set(DEFAULT_WEIGHTS):
        raise ValueError('Укажите веса для всех четырёх критериев')
    for k, v in values.items():
        if isinstance(v, bool) or not isinstance(v, (int, float)) or not math.isfinite(v) or not 0 <= v <= 100:
            raise ValueError('Вес каждого критерия должен быть числом от 0 до 100')
    if not any(v > 0 for v in values.values()):
        raise ValueError('Хотя бы один критерий должен иметь положительный вес')
    scores = {} if reliability is None else dict(reliability)
    if len(scores) > 10:
        raise ValueError('Слишком много оценок надёжности')
    for k, v in scores.items():
        if not isinstance(k, str) or len(k) > 100 or (supplier_names is not None and k not in supplier_names):
            raise ValueError('Неизвестный поставщик')
        if isinstance(v, bool) or not isinstance(v, (int, float)) or not math.isfinite(v) or not 0 <= v <= 100:
            raise ValueError('Оценка надёжности должна быть от 0 до 100')
    return {k: float(v) for k, v in values.items()}, {k: float(v) for k, v in scores.items()}

def _fact(supplier: dict[str, Any], key: str) -> float | None:
    for fact in supplier.get('facts', []):
        if fact.get('key') == key:
            val = fact.get('value')
            if isinstance(val, (int, float)) and math.isfinite(val):
                return float(val)
    return None

def build_ranking(result: dict[str, Any], weights: dict[str, float] | None = None,
                  reliability: dict[str, float] | None = None) -> dict[str, Any]:
    suppliers = result.get('suppliers', [])
    names = {s['name'] for s in suppliers}
    weights, reliability = clean_inputs(weights, reliability, names)
    eligible = [s for s in suppliers if result.get('requirements') and
                s.get('mandatory_failed', s.get('failed', 0)) == 0 and
                s.get('mandatory_unknown', s.get('unknown', 0)) == 0 and s.get('checks')]
    excluded = [{'supplier': s['name'], 'reason':
                 'Нарушены обязательные требования' if s.get('mandatory_failed', s.get('failed', 0)) else
                 'Недостаточно подтверждённых данных для соответствия ТЗ'}
                for s in suppliers if s not in eligible]
    if not eligible:
        return {'weights': weights, 'reliability': reliability, 'active_criteria': [],
                'unavailable': [], 'ranked': [], 'excluded': excluded,
                'recommended': None, 'warning': 'Нет поставщиков с подтверждённым соответствием требованиям.'}

    price = {s['name']: _fact(s, 'price') for s in eligible}
    days = {s['name']: _fact(s, 'delivery') for s in eligible}
    completeness = {
        'compliance': True,
        'price': all(v is not None and v > 0 for v in price.values()),
        'delivery': all(v is not None and v >= 0 for v in days.values()),
        'reliability': all(s['name'] in reliability for s in eligible),
    }
    active = [key for key, weight in weights.items() if weight > 0 and completeness[key]]
    unavailable = [LABELS[key] for key, weight in weights.items() if weight > 0 and not completeness[key]]
    if not active:
        return {'weights': weights, 'reliability': reliability, 'active_criteria': [],
                'unavailable': unavailable, 'ranked': [], 'excluded': excluded,
                'recommended': None, 'warning': 'Не хватает исходных данных для выбранных критериев.'}

    total_weight = sum(weights[k] for k in active)
    min_price = min(price.values()) if 'price' in active else None
    min_days = min(days.values()) if 'delivery' in active else None
    ranked = []
    for supplier in eligible:
        name = supplier['name']
        checks = supplier['checks']
        score_by_key = {
            'compliance': 100.0 * supplier.get('passed', 0) / len(checks),
            'price': 100.0 * min_price / price[name] if min_price is not None else None,
            'delivery': 100.0 if min_days == 0 and days.get(name) == 0 else
                        0.0 if min_days == 0 else
                        100.0 * min_days / days[name] if min_days is not None else None,
            'reliability': reliability.get(name),
        }
        components = {}
        for key in active:
            share = weights[key] / total_weight
            components[key] = {
                'label': LABELS[key], 'score': round(score_by_key[key], 2),
                'effective_weight': round(share * 100, 2),
                'contribution': round(score_by_key[key] * share, 2),
            }
        score = sum(score_by_key[k] * weights[k] / total_weight for k in active)
        ranked.append({'supplier': name, 'score': round(score, 2), 'components': components,
                       'eligibility': 'verified_numeric_requirements_only'})
    ranked.sort(key=lambda x: (-x['score'], x['supplier'].casefold()))
    tied = len(ranked) > 1 and abs(ranked[0]['score'] - ranked[1]['score']) < 0.01
    recommended = None if tied else ranked[0]['supplier']
    warning = ('Равные баллы: победителя без дополнительных критериев не определяем.' if tied else
               'Рейтинг предварительный: нечисловые условия и надёжность требуют проверки специалиста.')
    if unavailable:
        warning += ' Не учтены критерии без полных данных: ' + ', '.join(unavailable) + '.'
    return {'weights': weights, 'reliability': reliability, 'active_criteria': active,
            'unavailable': unavailable, 'ranked': ranked, 'excluded': excluded,
            'recommended': recommended, 'warning': warning}

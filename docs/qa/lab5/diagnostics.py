"""Collect SQL evidence separately from the HTTP load test."""
from statistics import median
from time import perf_counter

from django.db import connection
from django.test import Client
from django.test.utils import CaptureQueriesContext

from shop.models import Part


def catalog_diagnostics():
    client = Client()
    if client.get('/parts/').status_code != 200:
        raise RuntimeError('Дымовая проверка каталога завершилась ошибкой.')
    samples = []
    for _ in range(15):
        start = perf_counter()
        with CaptureQueriesContext(connection) as queries:
            response = client.get('/parts/')
        if response.status_code != 200:
            raise RuntimeError('Не удалось измерить SQL каталога.')
        samples.append({
            'elapsed_ms': round((perf_counter() - start) * 1000, 3),
            'sql_ms_rounded': round(sum(float(q['time']) for q in queries) * 1000, 3),
            'queries': len(queries),
            'body_bytes': len(response.content),
        })
    parts = Part.objects.filter(is_active=True).select_related('product_type', 'manufacturer').order_by('name')
    return {
        'catalog_rows': parts.count(),
        'median_elapsed_ms': median(s['elapsed_ms'] for s in samples),
        'median_sql_ms_rounded': median(s['sql_ms_rounded'] for s in samples),
        'plan': parts.explain().splitlines(),
        'samples': samples,
    }

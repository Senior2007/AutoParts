"""Basic access and audit checks restricted to synthetic fixtures in the QA copy."""
import io
import json
import logging
import os
import re
import sys
from pathlib import Path
from statistics import median
from time import perf_counter

os.environ.setdefault('DJANGO_DEBUG', 'False')
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'stand'))

from fixtures import PASSWORD, PHONE, buyer, part, require_scratch_database

import requests
import responses
from django.db import transaction
from django.test import Client, override_settings
from django.utils import timezone
from shop.models import Order, OrderItem, Sale

HIDDEN_MARKERS = {
    'traceback': r'traceback|stack trace',
    'server_path': r'/Users/|/private/var/|/usr/local/lib/',
    'sql': r'\bselect\b.{0,120}\bfrom\b|\binsert\s+into\b',
    'django_debug': r'id="traceback"|exception location',
}


def clues(response):
    body = response.content.decode(errors='replace')
    return [label for label, marker in HIDDEN_MARKERS.items() if re.search(marker, body, re.I)]


def order_for(user, item):
    order = Order.objects.create(
        user=user, client=user.client_profile, full_name='Иван Тестов', email=user.email,
        phone=PHONE, payment_method='erip', total=item.price,
    )
    OrderItem.objects.create(order=order, part=item, quantity=1, unit_price=item.price)
    return order


def run(base):
    require_scratch_database()
    records = []

    def result(id, title, expected, value, passed):
        records.append(dict(id=id, title=title, expected=expected, actual=value, status='PASS' if passed else 'FAIL'))

    with transaction.atomic(), override_settings(DEBUG=False):
        a, b = buyer('qa_sec_a'), buyer('qa_sec_b')
        p_a, p_b = part('sec-owner'), part('sec-other')
        first, second = order_for(a, p_a), order_for(b, p_b)
        guest = Client(enforce_csrf_checks=True, raise_request_exception=False)
        urls = ['/profile/', '/profile/complete/', '/checkout/', first.get_absolute_url(),
                '/reviews/add/', '/stats/', '/stats/chart.png', '/api/parts/']
        redirects = {url: (r.status_code, r.headers.get('Location')) for url in urls if (r := guest.get(url))}
        result('SEC-01', 'Защищённые URL без входа', 'Все 8 ответов 302 на вход.',
               redirects, len(redirects) == 8 and all(x[0] == 302 and x[1].startswith('/login/?next=') for x in redirects.values()))

        a_session = Client(enforce_csrf_checks=True, raise_request_exception=False)
        a_session.force_login(a)
        a_session.get('/profile/')
        csrf = a_session.cookies['csrftoken'].value
        access = {
            'own_confirmation': a_session.get(first.get_absolute_url()).status_code,
            'other_confirmation': a_session.get(second.get_absolute_url()).status_code,
        }
        for action in ['pay', 'cancel']:
            access['other_' + action] = a_session.post(f'/orders/{second.pk}/{action}/',
                                                       HTTP_X_CSRFTOKEN=csrf).status_code
        second.refresh_from_db()
        p_b.refresh_from_db()
        access.update(other_state=second.status, other_stock=p_b.quantity,
                      other_sales=Sale.objects.filter(part=p_b).count())
        result('SEC-02', 'Изоляция заказа второго клиента', 'Свой ответ 200, чужие ответы 404, new / 5 / 0 без изменений.',
               access, access == dict(own_confirmation=200, other_confirmation=404, other_pay=404,
                                      other_cancel=404, other_state='new', other_stock=5, other_sales=0))

        invalid_methods = {}
        for url in [f'/cart/add/{p_a.pk}/', f'/cart/update/{p_a.pk}/', f'/cart/remove/{p_a.pk}/',
                    '/cart/clear/', f'/orders/{first.pk}/pay/', f'/orders/{first.pk}/cancel/']:
            invalid_methods[url] = [a_session.get(url).status_code, a_session.post(url).status_code]
        result('SEC-03', 'Запрет изменяющих GET и POST без CSRF',
               'На выбранных изменяющих маршрутах GET → 405, POST без токена → 403.',
               invalid_methods, all(codes == [405, 403] for codes in invalid_methods.values()))

        statuses = {}
        for url in ['/api/qa-missing/', '/parts/?type=abc']:
            r = guest.get(url)
            statuses[url] = dict(status=r.status_code, markers=clues(r))
        result('SEC-04', 'Неразглашение деталей ошибок при DEBUG=False',
               'Ответы 404/500 не содержат трассировки, путей или SQL.',
               statuses, [item['status'] for item in statuses.values()] == [404, 500]
               and all(not item['markers'] for item in statuses.values()))
        with override_settings(DEBUG=True):
            debug = {}
            for url in ['/api/qa-missing/', '/parts/?type=abc']:
                r = guest.get(url)
                debug[url] = dict(status=r.status_code, markers=clues(r))
        result('SEC-05', 'Детали ошибок при значении DEBUG по умолчанию',
               'Пользователь не получает техническую информацию и трассировку.',
               debug, all(not item['markers'] for item in debug.values()))

        capture = io.StringIO()
        handler = logging.StreamHandler(capture)
        handler.setFormatter(logging.Formatter('%(name)s | %(levelname)s | %(message)s'))
        app_log = logging.getLogger('shop')
        request_log = logging.getLogger('django.request')
        app_log.addHandler(handler)
        request_log.addHandler(handler)
        try:
            events = {}
            guest.get('/login/')
            guest.post('/login/', {'username': a.username, 'password': PASSWORD,
                                   'csrfmiddlewaretoken': guest.cookies['csrftoken'].value})
            events['login'] = guest.session.get('_auth_user_id') == str(a.pk)
            csrf = guest.cookies['csrftoken'].value
            r = guest.post('/contacts/', dict(name='Иван', email='qa.audit@example.test', phone=PHONE,
                           topic='order', message='Синтетическая заявка аудита.', contact_method='phone', agree='on'),
                           HTTP_X_CSRFTOKEN=csrf)
            events['feedback'] = r.status_code == 302
            with responses.RequestsMock() as stub:
                for url in ['https://catfact.ninja/fact', 'https://api.ipify.org?format=json']:
                    stub.get(url, status=503)
                events['external'] = guest.get('/external-apis/').status_code == 200
            events['http404'] = guest.get('/api/qa-missing/').status_code == 404
            events['http500'] = guest.get('/parts/?type=abc').status_code == 500
            success = guest.post(f'/orders/{first.pk}/pay/', HTTP_X_CSRFTOKEN=csrf)
            first.refresh_from_db()
            events['payment'] = success.status_code == 302 and first.status == 'paid'
            canceled = order_for(a, p_a)
            res = guest.post(f'/orders/{canceled.pk}/cancel/', HTTP_X_CSRFTOKEN=csrf)
            canceled.refresh_from_db()
            events['cancel'] = res.status_code == 302 and canceled.status == 'canceled'
        finally:
            app_log.removeHandler(handler)
            request_log.removeHandler(handler)
        logs = capture.getvalue().splitlines()
        seen = {
            'feedback': any('Feedback from qa.audit' in x for x in logs),
            'external': sum('External API failed:' in x for x in logs),
            'http404': any('WARNING | Not Found:' in x for x in logs),
            'http500': any('ERROR | Internal Server Error:' in x for x in logs),
            'login': any(re.search(r'\b(login|logged in|authenticated)\b', x, re.I) for x in logs if x.startswith('shop')),
            'payment': any(re.search(r'\b(pay|paid|payment)\b', x, re.I) for x in logs if x.startswith('shop')),
            'cancel': any(re.search(r'\b(cancel|canceled|cancelled)\b', x, re.I) for x in logs if x.startswith('shop')),
        }
        result('SEC-06', 'Журнал ошибок и обратной связи', 'INFO заявки, два WARNING интеграций, WARNING 404 и ERROR 500.',
               dict(performed=events, logged=seen, entries=[x for x in logs if ' | ' in x]),
               all(events.values()) and seen['feedback'] and seen['external'] == 2 and seen['http404'] and seen['http500'])
        result('SEC-07', 'Аудит основных операций', 'Вход, оплата и отмена оставляют прикладное событие с результатом.',
               dict(performed={k: events[k] for k in ['login', 'payment', 'cancel']},
                    logged={k: seen[k] for k in ['login', 'payment', 'cancel']}),
               all(events[k] and seen[k] for k in ['login', 'payment', 'cancel']))
        result('SEC-08', 'Хранение пароля', 'Сохранён хеш, исходный пароль проверяется.',
               dict(plaintext=a.password == PASSWORD, matches=a.check_password(PASSWORD)),
               a.password != PASSWORD and a.check_password(PASSWORD))
        transaction.set_rollback(True)

    if base:
        samples = []
        with requests.Session() as session:
            for _ in range(21):
                start = perf_counter()
                response = session.get(base + '/parts/', timeout=5)
                samples.append(dict(status=response.status_code, ms=round((perf_counter() - start) * 1000, 2)))
        samples = samples[1:]
        result('PERF-01', 'Отклик каталога на стенде', 'Каждый из 20 последовательных запросов → 200 и ≤1000 мс.',
               dict(samples=samples, median_ms=median(x['ms'] for x in samples), max_ms=max(x['ms'] for x in samples)),
               all(x['status'] == 200 and x['ms'] <= 1000 for x in samples))

    return dict(date=str(timezone.localdate()), results=records)


if __name__ == '__main__':
    data = run(sys.argv[2].rstrip('/') if len(sys.argv) > 2 else '')
    Path(sys.argv[1]).write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding='utf-8')

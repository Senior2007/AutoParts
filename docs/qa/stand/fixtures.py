"""Synthetic fixtures for the supplemental suite. Use only with a scratch database."""
import json
import os
import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path.cwd()))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
import django

django.setup()

from django.conf import settings
from django.contrib.auth import get_user_model
from django.db import transaction
from shop.models import Client, Employee, Manufacturer, Part, ProductType

PASSWORD = 'DemoQA!926432'
PHONE = '+375 (29) 123-45-67'


def buyer(username, profile=True, staff=False):
    user = get_user_model().objects.create_user(
        username, password=PASSWORD, is_staff=staff,
        first_name='Иван', last_name='Тестов', email=f'{username}@example.test',
    )
    if profile:
        Client.objects.create(
            user=user, first_name=user.first_name, last_name=user.last_name,
            birth_date=date(1990, 1, 1), email=user.email, phone=PHONE, address='Минск',
        )
    return user


def part(key, name=None, **overrides):
    kind, _ = ProductType.objects.get_or_create(name='Контрольные фильтры')
    brand, _ = Manufacturer.objects.get_or_create(name='QA Bosch', defaults={'country': 'Германия'})
    fields = dict(sku=f'QA-{key}', name=name or f'Деталь QA {key}', price='100.00',
                  quantity=5, product_type=kind, manufacturer=brand,
                  description='Синтетическая запчасть для проверки магазина.')
    fields.update(overrides)
    return Part.objects.create(**fields)


def require_scratch_database():
    database = settings.DATABASES['default']
    if (database['ENGINE'] != 'django.db.backends.sqlite3'
            or not (Path.cwd() / '.qa-scratch').is_file()):
        raise SystemExit('Use the standalone SQLite copy with a .qa-scratch marker.')


@transaction.atomic
def seed_ui(mode, key):
    if mode == 'large':
        test_type = ProductType.objects.create(name=f'QA набор {key}')
        data = [
            part(f'{key}-{n}', name=f'QA{key} ' + ('СверхдлинноеНазвание' * 8 if n == 1 else str(n)),
                 product_type=test_type) for n in range(1, 66)
        ]
        data.append(part(f'{key}-short', name='Я', product_type=test_type))
        print(json.dumps({'typeId': test_type.pk, 'longName': data[0].name, 'count': len(data)}))
        return
    item = part(key, name=f'QA деталь {key}')
    print(json.dumps({'id': item.pk, 'name': item.name}))


@transaction.atomic
def seed_api():
    if get_user_model().objects.filter(username='qa_staff').exists():
        print('API fixtures already present')
        return
    buyer('qa_staff', profile=False, staff=True)
    buyer('qa_unprofiled', profile=False)
    part('API-PART', 'QA Контрольный фильтр', price='123.45', quantity=40)
    Employee.objects.create(first_name='Мария', last_name='Проверова', position='Менеджер',
                            responsibilities='Тестовый каталог', phone=PHONE, birth_date=date(1990, 1, 1),
                            email='qa.employee@example.test')
    print('API fixtures created')


if __name__ == '__main__':
    require_scratch_database()
    if sys.argv[1:] == ['api']:
        seed_api()
    elif len(sys.argv) == 4 and sys.argv[1] == 'ui' and sys.argv[2] in {'part', 'large'}:
        seed_ui(sys.argv[2], sys.argv[3])
    else:
        raise SystemExit('Usage: fixtures.py api | ui part/large unique-key')

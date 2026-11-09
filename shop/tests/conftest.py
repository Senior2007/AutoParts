"""Общие фикстуры. Каждый тест получает чистую БД (транзакция откатывается после теста),
поэтому тесты не зависят друг от друга и от порядка запуска."""
from datetime import date, timedelta
from decimal import Decimal

import pytest
from django.contrib.auth.models import User
from django.utils import timezone

from shop.models import Client, Manufacturer, Part, ProductType, PromoCode


@pytest.fixture
def product_type(db):
    return ProductType.objects.create(name='Фильтры')


@pytest.fixture
def manufacturer(db):
    return Manufacturer.objects.create(name='Bosch', country='Germany')


@pytest.fixture
def make_part(product_type, manufacturer):
    counter = {'n': 0}

    def _make(**fields):
        counter['n'] += 1
        data = {
            'sku': f'SKU-{counter["n"]}',
            'name': 'Масляный фильтр',
            'product_type': product_type,
            'manufacturer': manufacturer,
            'price': Decimal('100.00'),
            'quantity': 5,
            'description': 'Тестовый товар',
        }
        data.update(fields)
        return Part.objects.create(**data)

    return _make


@pytest.fixture
def part(make_part):
    return make_part()


@pytest.fixture
def make_buyer(db):
    def _make(username='buyer', email='buyer@example.com'):
        user = User.objects.create_user(username, password='buyer12345', email=email)
        Client.objects.create(
            user=user,
            first_name='Илья',
            last_name='Мартынов',
            birth_date=date(1994, 2, 14),
            phone='+375 (33) 201-21-31',
            email=email,
            address='Минск',
        )
        return user

    return _make


@pytest.fixture
def buyer(make_buyer):
    return make_buyer()


@pytest.fixture
def buyer_client(client, buyer):
    client.force_login(buyer)
    return client


@pytest.fixture
def staff_user(db):
    return User.objects.create_user('manager', password='manager12345', is_staff=True)


@pytest.fixture
def promo(db):
    today = timezone.localdate()
    return PromoCode.objects.create(
        code='ORDER10',
        description='Скидка 10%',
        discount_percent=10,
        starts_at=today - timedelta(days=1),
        ends_at=today + timedelta(days=30),
    )


@pytest.fixture
def checkout_data():
    def _data(**extra):
        data = {
            'full_name': 'Мартынов Илья',
            'phone': '+375 (33) 201-21-31',
            'email': 'buyer@example.com',
            'delivery_method': 'pickup',
            'delivery_address': '',
            'payment_method': 'card',
            'promo_code': '',
            'comment': '',
            'card_number': '4111 1111 1111 1111',
            'card_holder': 'ILYA MARTYNOV',
            'card_expiry': '2030-01',
            'card_cvc': '123',
            'agree': 'on',
        }
        data.update(extra)
        return data

    return _data

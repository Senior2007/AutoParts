"""Интеграционные тесты: компоненты работают вместе с настоящей тестовой БД,
ORM, формами и представлениями. Внешние HTTP-сервисы заменены заглушками `responses`."""
from decimal import Decimal

import pytest
import requests
import responses
from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.urls import reverse

from shop.forms import RegistrationForm
from shop.models import Client, Manufacturer, Order, OrderItem, Part, ProductType, Sale

pytestmark = pytest.mark.django_db

CAT_URL = 'https://catfact.ninja/fact'
IP_URL = 'https://api.ipify.org'


# ---------- Модели + БД ----------

def test_sale_decreases_stock_in_db(part, buyer):
    # Arrange
    client = buyer.client_profile
    # Act
    Sale.objects.create(client=client, part=part, quantity=2, unit_price=part.price)
    # Assert
    part.refresh_from_db()
    assert part.quantity == 3


def test_sale_more_than_stock_is_rejected_and_stock_unchanged(part, buyer):
    with pytest.raises(ValidationError):
        Sale.objects.create(client=buyer.client_profile, part=part, quantity=6, unit_price=part.price)
    part.refresh_from_db()
    assert part.quantity == 5
    assert Sale.objects.count() == 0


@pytest.mark.parametrize('promo_types, expected', [
    ([], True),                 # без ограничений — для любого товара
    (['Фильтры'], True),        # тип товара совпадает
    (['Тормоза'], False),       # другой тип
])
def test_promo_applies_to_part_by_product_type(promo, part, promo_types, expected):
    # Arrange
    for name in promo_types:
        promo.product_types.add(ProductType.objects.get_or_create(name=name)[0])
    # Act / Assert
    assert promo.applies_to_part(part) is expected


def test_order_pay_writes_sales_and_decreases_stock(part, buyer):
    # Arrange
    order = Order.objects.create(user=buyer, client=buyer.client_profile, full_name='Мартынов Илья',
                                 phone='+375 (33) 201-21-31', email='buyer@example.com', total=Decimal('200'))
    OrderItem.objects.create(order=order, part=part, quantity=2, unit_price=part.price)
    # Act
    order.pay()
    # Assert
    order.refresh_from_db()
    part.refresh_from_db()
    assert order.status == Order.STATUS_PAID
    assert order.paid_at is not None
    assert part.quantity == 3
    assert Sale.objects.filter(part=part, quantity=2).count() == 1


def test_order_pay_without_items_is_rejected(buyer):
    order = Order.objects.create(user=buyer, client=buyer.client_profile, full_name='Мартынов Илья',
                                 phone='+375 (33) 201-21-31', email='buyer@example.com')
    with pytest.raises(ValidationError):
        order.pay()
    order.refresh_from_db()
    assert order.status == Order.STATUS_NEW


# ---------- Формы + БД ----------

def registration_data(**extra):
    data = {
        'username': 'newbuyer',
        'first_name': 'Новый',
        'last_name': 'Покупатель',
        'birth_date': '1995-05-05',
        'phone': '+375 (29) 555-66-77',
        'email': 'newbuyer@example.com',
        'address': 'Минск',
        'password1': 'StrongPass12345',
        'password2': 'StrongPass12345',
    }
    data.update(extra)
    return data


def test_registration_creates_user_and_client_profile():
    # Arrange
    form = RegistrationForm(data=registration_data())
    # Act
    assert form.is_valid(), form.errors
    user = form.save()
    # Assert
    assert User.objects.filter(username='newbuyer').exists()
    assert Client.objects.get(user=user).phone == '+375 (29) 555-66-77'
    assert user.check_password('StrongPass12345')
    assert user.password != 'StrongPass12345'  # пароль хранится в виде хеша


@pytest.mark.parametrize('changes, error_field', [
    ({'email': 'buyer@example.com'}, 'email'),       # email уже занят
    ({'birth_date': '2015-01-01'}, 'birth_date'),    # младше 18
    ({'phone': '123'}, 'phone'),
    ({'password2': 'Other12345'}, 'password2'),
])
def test_registration_rejects_invalid_data(buyer, changes, error_field):
    form = RegistrationForm(data=registration_data(**changes))
    assert not form.is_valid()
    assert error_field in form.errors
    assert not User.objects.filter(username='newbuyer').exists()


# ---------- Представления + БД ----------

@pytest.mark.parametrize('query, expected_names', [
    ('Масляный', ['Масляный фильтр']),
    ('BOSCH', ['Масляный фильтр']),   # поиск по производителю без учета регистра (латиница)
    ('Тормоз', ['Тормозной диск']),
    ('brembo', ['Тормозной диск']),
    ('нет такого', []),
])
def test_catalog_search(client, make_part, query, expected_names):
    # Arrange
    make_part(name='Масляный фильтр')
    make_part(name='Тормозной диск', manufacturer=Manufacturer.objects.create(name='Brembo', country='Italy'))
    # Act
    response = client.get(reverse('part_list'), {'q': query})
    # Assert
    assert [p.name for p in response.context['parts']] == expected_names


@pytest.mark.parametrize('sort, expected_prices', [
    ('price', [Decimal('10.00'), Decimal('50.00'), Decimal('90.00')]),
    ('price_desc', [Decimal('90.00'), Decimal('50.00'), Decimal('10.00')]),
    ('unknown', [Decimal('10.00'), Decimal('50.00'), Decimal('90.00')]),  # неизвестная сортировка -> по имени
])
def test_catalog_sort(client, make_part, sort, expected_prices):
    make_part(name='A', price=Decimal('10.00'))
    make_part(name='B', price=Decimal('50.00'))
    make_part(name='C', price=Decimal('90.00'))
    response = client.get(reverse('part_list'), {'sort': sort})
    assert [p.price for p in response.context['parts']] == expected_prices


def test_catalog_hides_inactive_parts(client, make_part):
    make_part(name='Видимый')
    make_part(name='Удаленный', is_active=False)
    response = client.get(reverse('part_list'))
    assert [p.name for p in response.context['parts']] == ['Видимый']


@pytest.mark.parametrize('who, expected_status', [('anon', 302), ('client', 302), ('staff', 200)])
def test_stats_available_only_for_staff(client, buyer, staff_user, who, expected_status):
    if who == 'client':
        client.force_login(buyer)
    if who == 'staff':
        client.force_login(staff_user)
    assert client.get(reverse('stats')).status_code == expected_status


def test_parts_api_hides_sku_for_client_and_shows_for_staff(client, part, buyer, staff_user):
    assert client.get(reverse('parts_api')).status_code == 302
    client.force_login(buyer)
    assert 'sku' not in client.get(reverse('parts_api')).json()['results'][0]
    client.force_login(staff_user)
    assert client.get(reverse('parts_api')).json()['results'][0]['sku'] == part.sku


def test_staff_soft_deletes_part(client, part, staff_user):
    client.force_login(staff_user)
    response = client.post(reverse('part_delete', args=[part.pk]))
    part.refresh_from_db()
    assert response.status_code == 302
    assert part.is_active is False
    assert Part.objects.filter(pk=part.pk).exists()  # запись не удалена физически


def test_client_cannot_create_part(buyer_client):
    response = buyer_client.get(reverse('part_create'))
    assert response.status_code == 302
    assert reverse('login') in response['Location']


# ---------- Внешние сервисы: заглушки HTTP через responses ----------

@responses.activate
def test_external_apis_page_shows_data_from_services(client):
    # Arrange: подменяем ответы внешних сервисов на уровне HTTP
    responses.get(CAT_URL, json={'fact': 'Кошки спят 16 часов'})
    responses.get(IP_URL, json={'ip': '10.20.30.40'})
    # Act
    response = client.get(reverse('external_apis'))
    # Assert
    assert response.status_code == 200
    assert 'Кошки спят 16 часов' in response.content.decode()
    assert '10.20.30.40' in response.content.decode()
    assert len(responses.calls) == 2
    assert responses.calls[1].request.url == IP_URL + '/?format=json'


@pytest.mark.parametrize('cat_stub', [
    {'status': 500, 'json': {}},
    {'body': requests.ConnectionError('нет сети')},
    {'body': requests.Timeout('долго')},
])
@responses.activate
def test_external_apis_page_survives_service_failure(client, cat_stub):
    # Arrange
    responses.get(CAT_URL, **cat_stub)
    responses.get(IP_URL, status=503)
    # Act
    response = client.get(reverse('external_apis'))
    # Assert
    content = response.content.decode()
    assert response.status_code == 200
    assert 'API временно недоступен' in content
    assert 'не удалось получить' in content

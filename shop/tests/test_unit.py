"""Модульные (юнит) тесты: проверяют отдельные классы и функции.
Зависимости (БД, сессия, HTTP, текущая дата) заменены моками — тесты не ходят в БД и сеть."""
from datetime import date, timedelta
from decimal import Decimal
from unittest.mock import Mock, patch
from zoneinfo import ZoneInfo

import pytest
import requests
from django.core.exceptions import ValidationError

from shop.cart import Cart
from shop.forms import CheckoutForm
from shop.models import (
    Order,
    OrderItem,
    Part,
    PromoCode,
    Vacancy,
    email_validator,
    phone_validator,
    validate_adult,
    validate_not_future,
)
from shop.timeinfo import format_utc_offset
from shop.views import _safe_api_get


# ---------- Корзина (сессия и запросы к БД заменены моками) ----------

class FakeSession(dict):
    modified = False


def make_request(cart=None):
    request = Mock()
    request.session = FakeSession()
    if cart is not None:
        request.session['cart'] = cart
    return request


def fake_part(pk=1, quantity=5):
    return Mock(pk=pk, quantity=quantity)


@pytest.mark.parametrize(
    'in_cart, add, replace, stock, expected',
    [
        (0, 1, False, 5, 1),     # обычное добавление
        (2, 2, False, 5, 4),     # добавление к имеющемуся
        (3, 1, True, 5, 1),      # замена количества
        (0, 10, False, 5, 5),    # больше остатка -> обрезается до остатка
        (0, 150, False, 500, 99),  # граница: не больше 99 шт.
        (0, 0, False, 5, 1),     # граница: ноль -> минимум 1
        (0, -3, False, 5, 1),    # некорректный ввод: отрицательное число
    ],
)
def test_cart_add_keeps_quantity_within_limits(in_cart, add, replace, stock, expected):
    # Arrange
    request = make_request({'1': in_cart} if in_cart else None)
    with patch('shop.cart.Part') as part_model:
        part_model.objects.filter.return_value.values_list.return_value = [1]
        cart = Cart(request)
    # Act
    result = cart.add(fake_part(quantity=stock), quantity=add, replace=replace)
    # Assert
    assert result == expected
    assert request.session['cart'] == {'1': expected}
    assert request.session.modified is True


def test_cart_remove_deletes_only_given_position():
    # Arrange
    request = make_request()
    cart = Cart(request)
    cart.add(fake_part(pk=1), 2)
    cart.add(fake_part(pk=2), 3)
    # Act
    cart.remove(fake_part(pk=1))
    # Assert
    assert request.session['cart'] == {'2': 3}
    assert len(cart) == 3


def test_cart_remove_missing_position_does_not_fail():
    # Arrange
    cart = Cart(make_request())
    # Act
    cart.remove(fake_part(pk=42))
    # Assert
    assert cart.is_empty


def test_cart_clear_empties_session():
    # Arrange
    request = make_request()
    cart = Cart(request)
    cart.add(fake_part(), 2)
    # Act
    cart.clear()
    # Assert
    assert cart.is_empty
    assert request.session['cart'] == {}


def test_cart_drops_parts_that_are_no_longer_available():
    # Arrange
    request = make_request({'1': 2, '2': 3})
    with patch('shop.cart.Part') as part_model:
        part_model.objects.filter.return_value.values_list.return_value = [1]
        # Act
        cart = Cart(request)
    # Assert
    part_model.objects.filter.assert_called_once_with(pk__in=[1, 2], is_active=True)
    assert request.session['cart'] == {'1': 2}
    assert len(cart) == 2


def test_cart_with_broken_session_value_starts_empty():
    # Arrange
    request = make_request(cart='не словарь')
    # Act
    cart = Cart(request)
    # Assert
    assert cart.is_empty
    assert len(cart) == 0


# ---------- Валидаторы ----------

@pytest.mark.parametrize('phone', ['+375 (29) 123-45-67', '+375 (44) 000-00-00', '+375 (25) 999-99-99', '+375 (33) 201-21-31'])
def test_phone_validator_accepts_belarus_format(phone):
    phone_validator(phone)  # не должно быть исключения


@pytest.mark.parametrize(
    'phone',
    ['80291234567', '+375 (17) 123-45-67', '+375 (29) 1234567', '+375(29)123-45-67', '', '+375 (29) 123-45-6a'],
)
def test_phone_validator_rejects_wrong_format(phone):
    with pytest.raises(ValidationError):
        phone_validator(phone)


@pytest.mark.parametrize('email, is_valid', [
    ('name@example.com', True),
    ('a.b+c@mail.by', True),
    ('no-at-sign.com', False),
    ('name@domain', False),
    ('name@.c', False),
])
def test_email_validator(email, is_valid):
    if is_valid:
        email_validator(email)
    else:
        with pytest.raises(ValidationError):
            email_validator(email)


@pytest.mark.parametrize('birth_date, is_adult', [
    (date(2008, 6, 15), True),   # ровно 18 лет — граница
    (date(2008, 6, 16), False),  # 18 исполнится завтра
    (date(1990, 1, 1), True),
    (date(2015, 1, 1), False),
])
def test_validate_adult_boundaries(birth_date, is_adult):
    with patch('shop.models.timezone.localdate', return_value=date(2026, 6, 15)):
        if is_adult:
            validate_adult(birth_date)
        else:
            with pytest.raises(ValidationError):
                validate_adult(birth_date)


def test_validate_not_future_rejects_tomorrow():
    with patch('shop.models.timezone.localdate', return_value=date(2026, 6, 15)):
        validate_not_future(date(2026, 6, 15))
        with pytest.raises(ValidationError):
            validate_not_future(date(2026, 6, 16))


# ---------- Модели без БД ----------

@pytest.mark.parametrize('pk, number', [(1, 'AP-000001'), (42, 'AP-000042'), (123456, 'AP-123456')])
def test_order_number_format(pk, number):
    assert Order(pk=pk).number == number


def test_order_item_total_price():
    item = OrderItem(quantity=3, unit_price=Decimal('2.50'))
    assert item.total_price == Decimal('7.50')


@pytest.mark.parametrize('image_url, expected_count', [
    ('https://img.example.com/a.jpg?w=900', 3),
    ('https://img.example.com/a.jpg?x=1&w=480', 3),
    ('https://img.example.com/a.jpg', 0),
    ('', 0),
])
def test_part_image_srcset(image_url, expected_count):
    srcset = Part(image_url=image_url).image_srcset
    assert len([s for s in srcset.split(', ') if s]) == expected_count


@pytest.mark.parametrize('is_active, starts, ends, expected', [
    (True, date(2026, 1, 1), date(2026, 12, 31), True),
    (True, date(2026, 6, 15), date(2026, 6, 15), True),   # граница: один день
    (True, date(2026, 6, 16), date(2026, 12, 31), False),  # еще не начался
    (True, date(2026, 1, 1), date(2026, 6, 14), False),   # уже закончился
    (False, date(2026, 1, 1), date(2026, 12, 31), False),  # выключен
])
def test_promo_is_current(is_active, starts, ends, expected):
    promo = PromoCode(is_active=is_active, starts_at=starts, ends_at=ends)
    with patch('shop.models.timezone.localdate', return_value=date(2026, 6, 15)):
        assert promo.is_current is expected


def test_promo_clean_rejects_end_before_start():
    promo = PromoCode(starts_at=date(2026, 6, 10), ends_at=date(2026, 6, 1))
    with pytest.raises(ValidationError):
        promo.clean()


def test_vacancy_clean_rejects_max_salary_below_min():
    vacancy = Vacancy(salary_min=Decimal('2000'), salary_max=Decimal('1000'))
    with pytest.raises(ValidationError):
        vacancy.clean()


# ---------- Переходы состояний заказа (save замокан) ----------

def test_cancel_new_order_sets_canceled_status():
    # Arrange
    order = Order(status=Order.STATUS_NEW)
    with patch.object(Order, 'save') as save:
        # Act
        order.cancel()
    # Assert
    assert order.status == Order.STATUS_CANCELED
    save.assert_called_once()


@pytest.mark.parametrize('status', [Order.STATUS_PAID, Order.STATUS_CANCELED])
def test_cancel_is_forbidden_for_finished_order(status):
    order = Order(status=status)
    with patch.object(Order, 'save') as save:
        with pytest.raises(ValidationError):
            order.cancel()
    save.assert_not_called()
    assert order.status == status


@pytest.mark.parametrize('status', [Order.STATUS_PAID, Order.STATUS_CANCELED])
def test_pay_is_forbidden_for_finished_order(status):
    order = Order(status=status)
    with patch.object(Order, 'save') as save:
        with pytest.raises(ValidationError):
            order.pay()
    save.assert_not_called()


# ---------- Форма оформления заказа ----------

@pytest.fixture
def form_data():
    return {
        'full_name': 'Мартынов Илья',
        'phone': '+375 (33) 201-21-31',
        'email': 'buyer@example.com',
        'delivery_method': 'pickup',
        'payment_method': 'card',
        'card_number': '4111 1111 1111 1111',
        'card_holder': 'ILYA MARTYNOV',
        'card_expiry': '2030-01',
        'card_cvc': '123',
        'agree': 'on',
    }


def test_checkout_form_valid_data_is_accepted(form_data):
    form = CheckoutForm(data=form_data)
    assert form.is_valid(), form.errors
    assert form.cleaned_data['card_number'] == '4111111111111111'  # пробелы удаляются


@pytest.mark.parametrize('changes, error_field', [
    ({'card_number': '4111 1111'}, 'card_number'),
    ({'card_number': '4111 1111 1111 111a'}, 'card_number'),
    ({'card_number': ''}, 'card_number'),
    ({'card_cvc': '12'}, 'card_cvc'),
    ({'card_holder': ''}, 'card_holder'),
    ({'delivery_method': 'courier', 'delivery_address': ''}, 'delivery_address'),
    ({'delivery_date': (date.today() - timedelta(days=1)).isoformat()}, 'delivery_date'),
    ({'phone': '80291234567'}, 'phone'),
    ({'agree': ''}, 'agree'),
    ({'payment_method': 'bitcoin'}, 'payment_method'),
])
def test_checkout_form_rejects_invalid_input(form_data, changes, error_field):
    # Arrange
    form_data.update(changes)
    # Act
    form = CheckoutForm(data=form_data)
    # Assert
    assert not form.is_valid()
    assert error_field in form.errors


def test_checkout_form_erip_does_not_require_card(form_data):
    form_data.update(payment_method='erip', card_number='', card_holder='', card_expiry='', card_cvc='')
    assert CheckoutForm(data=form_data).is_valid()


# ---------- Обращение к внешнему API (requests замокан) ----------

def test_safe_api_get_returns_json_on_success():
    # Arrange
    response = Mock()
    response.json.return_value = {'fact': 'Cats sleep a lot'}
    with patch('shop.views.requests.get', return_value=response) as get:
        # Act
        result = _safe_api_get('https://api.test/fact', fallback={'fact': '-'})
    # Assert
    assert result == {'fact': 'Cats sleep a lot'}
    get.assert_called_once_with('https://api.test/fact', timeout=2)


@pytest.mark.parametrize('error', [requests.Timeout(), requests.ConnectionError(), requests.HTTPError('500')])
def test_safe_api_get_returns_fallback_on_error(error):
    with patch('shop.views.requests.get', side_effect=error):
        assert _safe_api_get('https://api.test/fact', fallback={'fact': '-'}) == {'fact': '-'}


# ---------- Время ----------

@pytest.mark.parametrize('zone, expected', [
    ('Europe/Minsk', 'UTC+03:00'),
    ('UTC', 'UTC+00:00'),
    ('Asia/Kolkata', 'UTC+05:30'),
    ('America/Caracas', 'UTC-04:00'),
])
def test_format_utc_offset(zone, expected):
    assert format_utc_offset(ZoneInfo(zone)) == expected

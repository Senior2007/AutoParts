"""Сценарные тесты: цепочки HTTP-запросов, проводящие заказ по диаграмме состояний
(docs/state-diagram.md):  корзина -> new (Ожидает оплаты) -> paid (Оплачен) | canceled (Отменен)."""
import pytest
from django.contrib.messages import get_messages
from django.urls import reverse

from shop.models import Order, Sale

pytestmark = pytest.mark.django_db


def put_in_cart(http_client, part, quantity=2):
    http_client.post(reverse('cart_add', args=[part.pk]), {'quantity': quantity})


def place_order(http_client, checkout_data, payment_method):
    data = checkout_data(payment_method=payment_method)
    if payment_method != 'card':
        data.update(card_number='', card_holder='', card_expiry='', card_cvc='')
    return http_client.post(reverse('checkout'), data)


def test_card_payment_moves_order_from_cart_to_paid(buyer_client, part, checkout_data):
    # Arrange
    put_in_cart(buyer_client, part, 2)
    # Act
    response = place_order(buyer_client, checkout_data, 'card')
    # Assert
    order = Order.objects.get()
    assert response.status_code == 302
    assert response['Location'] == reverse('order_success', args=[order.pk])
    assert order.status == Order.STATUS_PAID
    assert order.paid_at is not None
    part.refresh_from_db()
    assert part.quantity == 3
    assert Sale.objects.count() == 1
    assert buyer_client.session['cart'] == {}
    assert buyer_client.get(reverse('order_success', args=[order.pk])).status_code == 200


@pytest.mark.parametrize('payment_method', ['erip', 'invoice'])
def test_deferred_payment_order_waits_then_becomes_paid(buyer_client, part, checkout_data, payment_method):
    # Arrange: корзина -> оформление (new)
    put_in_cart(buyer_client, part, 2)
    place_order(buyer_client, checkout_data, payment_method)
    order = Order.objects.get()
    part.refresh_from_db()
    assert order.status == Order.STATUS_NEW
    assert part.quantity == 5          # товар еще не списан
    assert Sale.objects.count() == 0
    # Act: new -> paid
    response = buyer_client.post(reverse('order_pay', args=[order.pk]))
    # Assert
    order.refresh_from_db()
    part.refresh_from_db()
    assert response['Location'] == reverse('order_success', args=[order.pk])
    assert order.status == Order.STATUS_PAID
    assert part.quantity == 3
    assert Sale.objects.count() == 1


def test_new_order_can_be_canceled(buyer_client, part, checkout_data):
    # Arrange
    put_in_cart(buyer_client, part, 2)
    place_order(buyer_client, checkout_data, 'erip')
    order = Order.objects.get()
    # Act: new -> canceled
    buyer_client.post(reverse('order_cancel', args=[order.pk]))
    # Assert
    order.refresh_from_db()
    part.refresh_from_db()
    assert order.status == Order.STATUS_CANCELED
    assert part.quantity == 5
    assert Sale.objects.count() == 0


@pytest.mark.parametrize('first_step, second_step, final_status', [
    ('order_pay', 'order_pay', Order.STATUS_PAID),          # повторная оплата
    ('order_pay', 'order_cancel', Order.STATUS_PAID),       # отмена оплаченного
    ('order_cancel', 'order_pay', Order.STATUS_CANCELED),   # оплата отмененного
    ('order_cancel', 'order_cancel', Order.STATUS_CANCELED),
])
def test_finished_order_does_not_change_state(buyer_client, part, checkout_data, first_step, second_step, final_status):
    # Arrange
    put_in_cart(buyer_client, part, 1)
    place_order(buyer_client, checkout_data, 'erip')
    order = Order.objects.get()
    buyer_client.post(reverse(first_step, args=[order.pk]))
    # Act
    response = buyer_client.post(reverse(second_step, args=[order.pk]))
    # Assert
    order.refresh_from_db()
    part.refresh_from_db()
    assert order.status == final_status
    assert Sale.objects.count() == (1 if final_status == Order.STATUS_PAID else 0)
    assert part.quantity == (4 if final_status == Order.STATUS_PAID else 5)
    assert any(m.level_tag == 'error' for m in get_messages(response.wsgi_request))


def test_pay_fails_when_stock_ran_out_and_order_stays_new(buyer_client, part, checkout_data):
    # Arrange
    put_in_cart(buyer_client, part, 2)
    place_order(buyer_client, checkout_data, 'erip')
    order = Order.objects.get()
    part.quantity = 1  # товар успели раскупить
    part.save()
    # Act
    response = buyer_client.post(reverse('order_pay', args=[order.pk]))
    # Assert
    order.refresh_from_db()
    assert response['Location'] == reverse('profile')
    assert order.status == Order.STATUS_NEW
    assert Sale.objects.count() == 0


@pytest.mark.parametrize('action', ['order_pay', 'order_cancel'])
def test_other_user_cannot_change_order(client, make_buyer, part, checkout_data, action):
    # Arrange
    owner = make_buyer('owner', 'owner@example.com')
    client.force_login(owner)
    put_in_cart(client, part, 1)
    place_order(client, checkout_data, 'erip')
    order = Order.objects.get()
    client.force_login(make_buyer('stranger', 'stranger@example.com'))
    # Act
    response = client.post(reverse(action, args=[order.pk]))
    # Assert
    assert response.status_code == 404
    order.refresh_from_db()
    assert order.status == Order.STATUS_NEW


@pytest.mark.parametrize('action', ['order_pay', 'order_cancel'])
def test_state_change_requires_post(buyer_client, action):
    assert buyer_client.get(reverse(action, args=[1])).status_code == 405


def test_guest_is_sent_to_login_and_no_order_created(client, part, checkout_data):
    put_in_cart(client, part, 1)
    response = place_order(client, checkout_data, 'card')
    assert reverse('login') in response['Location']
    assert Order.objects.count() == 0


def test_promo_code_is_applied_through_whole_scenario(buyer_client, part, promo, checkout_data):
    put_in_cart(buyer_client, part, 2)
    buyer_client.post(reverse('checkout'), checkout_data(promo_code='order10'))  # регистр не важен
    order = Order.objects.get()
    assert order.status == Order.STATUS_PAID
    assert order.discount_percent == 10
    assert str(order.total) == '180.00'
    assert str(Sale.objects.get().unit_price) == '90.00'

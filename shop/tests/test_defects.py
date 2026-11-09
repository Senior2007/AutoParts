"""Регрессионные тесты на дефекты из ISSUES.md.
Пока дефект не исправлен, тест помечен xfail(strict=True): он ожидаемо падает.
Когда дефект исправят, тест начнет проходить, pytest сообщит XPASS — тогда метку xfail снимают,
и тест остается в наборе, чтобы дефект не вернулся."""
import pytest
from django.urls import reverse

from shop.forms import FeedbackForm
from shop.models import Order, OrderItem

pytestmark = pytest.mark.django_db


@pytest.mark.xfail(strict=True, reason='BUG-1: нечисловой ?type= приводит к ошибке 500')
def test_bug1_catalog_with_text_type_filter_does_not_crash(client, part):
    response = client.get(reverse('part_list'), {'type': 'abc'})
    assert response.status_code == 200


@pytest.mark.xfail(strict=True, reason='BUG-2: открытый редирект через параметр next')
def test_bug2_cart_add_does_not_redirect_to_external_site(client, part):
    response = client.post(reverse('cart_add', args=[part.pk]), {'quantity': 1, 'next': 'https://evil.example.com'})
    assert not response['Location'].startswith('https://evil.example.com')


@pytest.mark.xfail(strict=True, reason='BUG-3: карточка удаленного товара открывается по прямой ссылке')
def test_bug3_deleted_part_page_is_not_found(client, make_part):
    deleted = make_part(is_active=False)
    assert client.get(reverse('part_detail', args=[deleted.pk])).status_code == 404


@pytest.mark.xfail(strict=True, reason='BUG-4: поиск по кириллице чувствителен к регистру (SQLite)')
def test_bug4_cyrillic_search_ignores_case(client, make_part):
    make_part(name='Амортизатор KYB')
    response = client.get(reverse('part_list'), {'q': 'амортизатор'})
    assert [p.name for p in response.context['parts']] == ['Амортизатор KYB']


@pytest.mark.xfail(strict=True, reason='BUG-5: страница подтверждения пишет «оплачен» для неоплаченного заказа')
def test_bug5_success_page_does_not_say_paid_for_new_order(buyer_client, buyer, part):
    order = Order.objects.create(user=buyer, client=buyer.client_profile, full_name='Мартынов Илья',
                                 phone='+375 (33) 201-21-31', email='buyer@example.com', payment_method='erip')
    OrderItem.objects.create(order=order, part=part, quantity=1, unit_price=part.price)
    response = buyer_client.get(reverse('order_success', args=[order.pk]))
    assert 'оплачен</h1>' not in response.content.decode()


@pytest.mark.xfail(strict=True, reason='BUG-6: год выпуска ограничен жестко заданным 2026')
def test_bug6_feedback_accepts_next_model_year():
    form = FeedbackForm()
    assert form.fields['production_year'].max_value >= 2027

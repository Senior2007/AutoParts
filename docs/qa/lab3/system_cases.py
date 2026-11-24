"""Repeatable Lab 3 system cases. Run via python -m docs.qa system."""
import io
import json
import logging
from datetime import timedelta
from decimal import Decimal

import responses
from django.contrib.auth import get_user_model
from django.db import transaction
from django.test import Client, override_settings
from django.test.utils import setup_test_environment
from django.utils import timezone
from requests import Timeout
from docs.qa.stand.fixtures import PASSWORD, PHONE, buyer, part, require_scratch_database
from shop.models import Client as BuyerProfile
from shop.models import Order, Part, ProductType, PromoCode, Review, Sale

CASES = []
User = get_user_model()
TODAY = timezone.localdate()


def case(req, priority, module, title, data, steps, expected, defect=''):
    def register(test):
        CASES.append((dict(id=f'TC-{len(CASES) + 1:02}', req=req, priority=priority,
                           module=module, title=title, data=data, steps=steps,
                           expected=expected, defect=defect), test))
        return test
    return register


class Scenario:
    def __init__(self):
        self.client = Client(raise_request_exception=False)
        self.notes = []
        self.last = None

    def call(self, url, data=None, client=None, follow=False):
        actor = client if client is not None else self.client
        if data is None:
            response = actor.get(url, follow=follow)
        else:
            response = actor.post(url, data, follow=follow)
        self.last = response
        chain = getattr(response, 'redirect_chain', [])
        suffix = f' → {response["Location"]}' if 'Location' in response else ''
        if chain:
            suffix = ' после ' + ', '.join(f'{code} {location}' for location, code in chain)
        self.notes.append(f'{"GET" if data is None else "POST"} {url} → {response.status_code}{suffix}')
        return response

    def login(self, username='qa_case', profile=True, staff=False):
        user = buyer(username, profile=profile, staff=staff)
        self.client.force_login(user)
        return user

    def observe(self, text):
        self.notes.append(text)


def require(condition, observation):
    if not condition:
        raise AssertionError(observation)


def names(response):
    require(response.status_code == 200, f'Каталог ответил HTTP {response.status_code}.')
    return list(response.context['parts'].values_list('name', flat=True))


def cart(s, item, quantity=2):
    return s.call(f'/cart/add/{item.pk}/', {'quantity': quantity})


def stock(item):
    item.refresh_from_db()
    return item.quantity


def checkout(s, user, **changes):
    data = dict(full_name='Тестов Иван', phone=PHONE, email=user.email, delivery_method='pickup',
                agree='on', payment_method='card', card_number='4111 1111 1111 1111',
                card_holder='IVAN TESTOV', card_expiry=f'{TODAY.year + 2}-01', card_cvc='123')
    data.update(changes)
    return s.call('/checkout/', data)


def latest(user):
    result = Order.objects.filter(user=user).first()
    require(result is not None, 'Заказ не создан.')
    return result


def registration(**changes):
    data = dict(username='qa_reg', first_name='Иван', last_name='Тестов',
                birth_date='1990-01-01', phone=PHONE, email='qa_reg@example.test',
                address='Минск', password1=PASSWORD, password2=PASSWORD)
    data.update(changes)
    return data


def feedback(**changes):
    data = dict(name='Иван', email='qa.feedback@example.test', phone=PHONE,
                topic='vin', vin='WVWZZZ1KZAW000001', production_year=2020,
                contact_method='phone', message='Нужен фильтр для автомобиля.', agree='on')
    data.update(changes)
    return data


@case('FR-01', 'Высокий', 'Каталог', 'Активность товара в выдаче', 'Одна активная и одна скрытая деталь QA.',
      ['Создать две детали с разным is_active.', 'Открыть каталог с q=QA.', 'Сопоставить выдачу с обеими деталями.'],
      'Активная отображается, скрытая отсутствует.')
def active(s):
    a = part('visible')
    b = part('hidden', is_active=False)
    values = names(s.call('/parts/?q=QA'))
    require(a.name in values and b.name not in values, 'Список расходится с флагами активности.')
    s.observe(f'Выдача содержит «{a.name}» и исключает «{b.name}».')


@case('FR-02', 'Высокий', 'Каталог', 'Подстрока в трёх полях и видимость артикула',
      'Деталь BetaPart, тип «Контрольные фильтры», изготовитель QA Bosch, артикул QA-X9ONLY.',
      ['Искать по betapa, контрольной подстроке и bosch.', 'Гостем искать X9ONLY.', 'Повторить поиск X9ONLY сотрудником.'],
      'Три общих запроса находят деталь. Артикул работает только для сотрудника.')
def search_fields(s):
    a = part('X9ONLY', 'BetaPart')
    for query in ['betapa', 'Контрольные', 'bosch']:
        require(a.name in names(s.call('/parts/?q=' + query)), f'Нет результата по {query}.')
    require(a.name not in names(s.call('/parts/?q=X9ONLY')), 'Артикул доступен гостю.')
    s.login('qa_search_staff', staff=True, profile=False)
    require(a.name in names(s.call('/parts/?q=X9ONLY')), 'Артикул не найден сотрудником.')


@case('FR-02', 'Высокий', 'Каталог', 'Регистр при поиске кириллицы', 'Товар «Амортизатор QA».',
      ['Выполнить поиск с прописной буквы.', 'Повторить со строчной.', 'Сравнить наличие контрольного товара.'],
      'Обе выдачи содержат контрольный товар.', 'BUG-4')
def search_unicode(s):
    a = part('cyrillic', 'Амортизатор QA')
    upper = a.name in names(s.call('/parts/?q=Амортизатор'))
    lower = a.name in names(s.call('/parts/?q=амортизатор'))
    s.observe(f'«Амортизатор» → {upper}; «амортизатор» → {lower}.')
    require(upper and lower, 'Товар найден только при совпадении регистра.')


@case('FR-03', 'Средний', 'Каталог', 'Фильтр типа и несуществующий ID', 'Две детали разных типов, ID 999999.',
      ['Открыть выбранный тип.', 'Проверить состав.', 'Подставить отсутствующий числовой ID.'],
      'При выбранном типе видна одна подходящая деталь. Отсутствующий ID игнорируется.')
def type_numeric(s):
    a = part('filter-a', 'QA type A')
    kind = ProductType.objects.create(name='Тестовая электрика')
    b = part('filter-b', 'QA type B', product_type=kind)
    require(names(s.call(f'/parts/?q=QA%20type&type={a.product_type_id}')) == [a.name], 'Фильтр выбрал другой тип.')
    result = names(s.call('/parts/?q=QA%20type&type=999999'))
    require(set(result) == {a.name, b.name}, 'Недействительный ID не был проигнорирован.')


@case('FR-03, NFR-04', 'Средний', 'Каталог', 'Нечисловой фильтр', 'type=abc.',
      ['Открыть каталог.', 'Повторить запрос с type=abc.', 'Сравнить код и выдачу.'],
      'HTTP 200 и прежняя выдача.', 'BUG-1')
def type_text(s):
    original = names(s.call('/parts/'))
    require(names(s.call('/parts/?type=abc')) == original, 'Невалидный фильтр изменил каталог.')


@case('FR-04', 'Средний', 'Каталог', 'Порядок сортировки и запасной вариант',
      'QA Sort A: 50 BYN и 2 шт.; QA Sort B: 25 BYN и 9 шт.',
      ['Запросить все четыре направления сортировки.', 'Проверить сортировку по умолчанию и sort=unknown.'],
      'Цена и количество сортируются в заданном направлении. Неизвестный режим даёт порядок по имени.')
def sorting(s):
    a = part('sort-a', 'QA Sort A', price='50.00', quantity=2)
    b = part('sort-b', 'QA Sort B', price='25.00', quantity=9)
    for mode, reverse in [('price', True), ('price_desc', False), ('quantity', False),
                          ('quantity_desc', True), ('unknown', False), ('name', False)]:
        expected = [b.name, a.name] if reverse else [a.name, b.name]
        require(names(s.call(f'/parts/?q=QA%20Sort&sort={mode}')) == expected, f'Неверный порядок для {mode}.')


@case('FR-05', 'Высокий', 'Каталог / Карточка', 'Поля карточки, похожие товары и отсутствующий ID',
      'Деталь 100 BYN, остаток 5; четыре похожих, один другой тип, ID 999999.',
      ['Открыть карточку.', 'Проверить цену, остаток и список похожих.', 'Запросить отсутствующую карточку.'],
      'Карточка показывает данные и ровно 3 подходящих товара; отсутствующий ID → 404.')
def detail(s):
    a = part('detail')
    for index in range(4):
        part(f'similar-{index}')
    part('other', product_type=ProductType.objects.create(name='Посторонний тип'))
    require(s.call('/parts/999999/').status_code == 404, 'Несуществующая карточка доступна.')
    res = s.call(f'/parts/{a.pk}/')
    shown = res.context['part']
    similar = list(res.context['similar_parts'])
    require(shown.name == a.name and shown.price == Decimal('100') and shown.quantity == 5
            and len(similar) == 3 and all(x.product_type_id == a.product_type_id and x != a for x in similar),
            'Поля или подбор аналогов неверны.')
    s.observe('Цена 100 BYN, остаток 5, похожих товаров 3.')


@case('FR-05', 'Высокий', 'Каталог / Карточка', 'Карточка после мягкого удаления',
      'Активная деталь и аккаунт сотрудника.',
      ['Удалить деталь сотрудником через форму.', 'Открыть её исходный URL гостем.'],
      'Удалённая карточка возвращает HTTP 404.', 'BUG-3')
def deleted_detail(s):
    actor = Client()
    actor.force_login(buyer('qa_delete_staff', profile=False, staff=True))
    a = part('deleted')
    s.call(f'/parts/{a.pk}/delete/', {}, actor)
    require(not Part.objects.get(pk=a.pk).is_active, 'Товар не деактивирован.')
    require(s.call(f'/parts/{a.pk}/').status_code == 404, 'Карточка скрытой позиции отвечает HTTP 200.')


@case('FR-06', 'Высокий', 'Корзина', 'Минимум, складской предел и потолок 99',
      'Позиции с остатками 5 и 150. Количества 0, 90 и 150.',
      ['Добавить первую позицию с количеством 0.', 'Добавить ещё 90 шт. первой позиции.', 'Добавить 150 шт. второй.'],
      'Границы применяются как 1, 5 и 99.')
def cart_limits(s):
    a = part('limit-a')
    b = part('limit-b', quantity=150)
    for item, amount, expected in [(a, 0, 1), (a, 90, 5), (b, 150, 99)]:
        cart(s, item, amount)
        require(s.client.session['cart'][str(item.pk)] == expected, f'Количество {expected} не получено.')
        s.observe(f'Количество {amount} обработано, итог {expected}.')
    s.call('/cart/')


@case('FR-06', 'Высокий', 'Корзина', 'Нет товара на складе', 'Активная позиция с остатком 0.',
      ['Открыть карточку.', 'Попробовать запрос добавления.', 'Проверить корзину.'],
      'Сообщение о нулевом остатке, корзина пустая.')
def cart_zero(s):
    item = part('zero', quantity=0)
    res = s.call(f'/cart/add/{item.pk}/', {'quantity': 1}, follow=True)
    require('нет на складе' in res.content.decode(), 'Нет сообщения о нулевом остатке.')
    require(len(s.call('/cart/').context['cart']) == 0, 'Позиция с нулевым остатком добавлена.')


@case('FR-07', 'Высокий', 'Корзина', 'Изменение количества, удаление и очистка',
      'Детали по 100 BYN, остаток 3 и 5.',
      ['Добавить 2 шт. первой, увеличить дважды и проверить предел.', 'Уменьшить 3→2→1→0.',
       'Добавить обе детали, удалить первую вручную и очистить корзину.'],
      'Суммы 200→300→300→200→100→0. Удаляется заданная позиция, очистка убирает всё.')
def cart_actions(s):
    a, b = part('actions-a', quantity=3), part('actions-b')
    cart(s, a)
    require(s.call('/cart/').context['cart_total'] == Decimal('200'), 'Начальная сумма не равна 200.')
    for action, expected in [('increase', 300), ('increase', 300), ('decrease', 200),
                             ('decrease', 100), ('decrease', 0)]:
        s.call(f'/cart/update/{a.pk}/', {'action': action})
        actual = s.call('/cart/').context['cart_total']
        require(actual == Decimal(expected), f'Итог {actual} вместо {expected}.')
        s.observe(f'Промежуточный итог {actual} BYN.')
    cart(s, a, 1)
    cart(s, b, 1)
    s.call(f'/cart/remove/{a.pk}/', {})
    require(s.client.session['cart'] == {str(b.pk): 1}, 'Удаление изменило другую позицию.')
    s.call('/cart/clear/', {})
    require(s.call('/cart/').context['cart_total'] == 0, 'После очистки корзина не пуста.')


@case('FR-08', 'Средний', 'Корзина', 'Автоудаление недоступных позиций',
      'Три позиции в одной корзине. Одну деактивировать, вторую физически удалить на стенде.',
      ['Добавить все три позиции.', 'Изменить доступность двух позиций в базе.', 'Открыть корзину.'],
      'Остаётся только активная существующая позиция.')
def cart_prunes(s):
    a, b, c = part('drop-a'), part('drop-b'), part('drop-c')
    for item in [a, b, c]:
        cart(s, item, 1)
    a.is_active = False
    a.save()
    b.delete()
    res = s.call('/cart/')
    require([row['part'].pk for row in res.context['cart']] == [c.pk], 'В корзине остались недоступные товары.')


@case('FR-09', 'Высокий', 'Оформление / Доступ', 'Гость и пустая корзина',
      'Гость с товаром; клиент с заполненным профилем и пустой корзиной.',
      ['Добавить деталь гостем и открыть checkout.', 'В независимой сессии клиента открыть checkout с пустой корзиной.'],
      'Гость перенаправлен на вход, клиент с пустой корзиной → каталог. Заказов нет.')
def checkout_access(s):
    cart(s, part('gate'), 1)
    guest = s.call('/checkout/')
    require(guest.status_code == 302 and guest.url.startswith('/login/?next='), 'Гость допущен к оформлению.')
    s.client = Client(raise_request_exception=False)
    u = s.login()
    empty = s.call('/checkout/')
    require(empty.status_code == 302 and empty.url == '/parts/' and not Order.objects.filter(user=u).exists(),
            'Пустая корзина прошла оформление.')
    s.call('/parts/')


@case('FR-09', 'Высокий', 'Оформление / Доступ', 'Заполненный и отсутствующий профиль',
      'Два аккаунта с корзинами, профиль у одного.',
      ['Открыть checkout с профилем.', 'Войти вторым аккаунтом, наполнить корзину и открыть checkout.'],
      'Клиенту форма доступна. Пользователь без профиля направлен на его заполнение.')
def checkout_profile(s):
    p = part('profile')
    s.login()
    cart(s, p)
    require(s.call('/checkout/').status_code == 200, 'Клиент не открыл оформление.')
    s.client = Client(raise_request_exception=False)
    s.login('qa_no_profile', profile=False)
    cart(s, p)
    res = s.call('/checkout/', follow=True)
    require(res.redirect_chain == [('/profile/complete/', 302)], 'Нет перенаправления на заполнение профиля.')


@case('FR-10, NFR-06', 'Высокий', 'Оформление / Валидация', 'Отклонение полей заказа',
      'Телефон 123, email bad, курьер/почта без адреса, вчерашняя дата, согласие снято, 15 цифр, пустые держатель/срок, CVC 12.',
      ['Сначала открыть корректную форму.', 'Отправить наборы с ошибками для курьера и почты.', 'Проверить поля, верхнюю сводку, корзину и отсутствие заказа.'],
      'Ошибочные поля перечислены над формой, заказ не сохранён, корзина остаётся.')
def checkout_invalid(s):
    u = s.login()
    p = part('invalid')
    cart(s, p, 1)
    for method in ['courier', 'post']:
        res = checkout(s, u, phone='123', email='bad', delivery_method=method,
                       delivery_date=str(TODAY - timedelta(days=1)), agree='',
                       card_number='411111111111111', card_holder='', card_expiry='', card_cvc='12')
        expected = {'phone', 'email', 'delivery_address', 'delivery_date', 'agree',
                    'card_number', 'card_holder', 'card_expiry', 'card_cvc'}
        errors = set(res.context['form'].errors)
        require(expected <= errors, f'Нет ошибок полей {expected - errors}.')
        body = res.content.decode()
        require('class="errorlist" role="alert"' in body and body.index('class="errorlist" role="alert"') < body.index('checkout-form'),
                'Сводка ошибок отсутствует над формой.')
    require(not Order.objects.filter(user=u).exists() and s.client.session['cart'] == {str(p.pk): 1},
            'Появился заказ или изменилась корзина.')


@case('FR-11', 'Высокий', 'Оформление / Промокоды', 'Активный промокод в другом регистре',
      'QAORDER10, период вчера–завтра, скидка 10%, 2 × 100 BYN.',
      ['Добавить 2 детали.', 'Оформить ЕРИП с qaorder10.', 'Проверить процент и сумму.'],
      'Скидка 10%, итог 180 BYN.')
def promo_valid(s):
    u = s.login()
    item = part('promo-valid')
    PromoCode.objects.create(code='QAORDER10', discount_percent=10,
                             starts_at=TODAY - timedelta(days=1), ends_at=TODAY + timedelta(days=1))
    cart(s, item)
    checkout(s, u, payment_method='erip', promo_code='qaorder10')
    order = latest(u)
    require(order.total == 180 and order.discount_percent == 10, f'Итог {order.total}, скидка {order.discount_percent}%.')
    s.observe(f'Итог {order.total} BYN, скидка {order.discount_percent}%.')
    s.call('/profile/')


@case('FR-11', 'Высокий', 'Оформление / Промокоды', 'Неизвестный, истёкший и отключённый промокоды',
      'QAMISSING, QAOLD с прошедшим периодом и QAINACTIVE с текущим, но отключённым периодом.',
      ['Подготовить корзину.', 'Отправить форму с каждым из трёх кодов.', 'Проверить сообщения и БД.'],
      'Три кода отклонены, заказ не создаётся.')
def promo_invalid(s):
    u = s.login()
    cart(s, part('promo-invalid'))
    PromoCode.objects.create(code='QAOLD', discount_percent=10, starts_at=TODAY - timedelta(days=5),
                             ends_at=TODAY - timedelta(days=1))
    PromoCode.objects.create(code='QAINACTIVE', discount_percent=10, is_active=False,
                             starts_at=TODAY, ends_at=TODAY + timedelta(days=1))
    for code in ['QAMISSING', 'QAOLD', 'QAINACTIVE']:
        res = checkout(s, u, promo_code=code)
        require('promo_code' in res.context['form'].errors, f'Код {code} принят.')
        s.observe(f'{code} отклонён.')
    require(not Order.objects.filter(user=u).exists(), 'Заказ сохранился с неверным промокодом.')


@case('FR-12, FR-10', 'Высокий', 'Заказы / Карта', 'Оплата картой и списание',
      'Клиент, 2 × 100 BYN при остатке 5, данные тестовой карты и адрес курьера.',
      ['Наполнить корзину.', 'Оформить и оплатить картой.', 'Проверить подтверждение, заказ, продажи, склад и корзину.'],
      'paid и paid_at заполнены, одна продажа на 2 шт., остаток 3, корзина пуста.')
def card_paid(s):
    u = s.login()
    p = part('card')
    cart(s, p)
    res = checkout(s, u, delivery_method='courier', delivery_address='Минск, ул. Тестовая, 1',
                   delivery_date=str(TODAY))
    o = latest(u)
    require(res.status_code == 302 and res.url == o.get_absolute_url() and o.status == 'paid' and o.paid_at
            and stock(p) == 3 and Sale.objects.filter(part=p, quantity=2).count() == 1 and not s.client.session['cart'],
            'Побочные эффекты оплаты не соответствуют требованиям.')
    s.observe(f'{o.number}: paid, paid_at заполнено, склад 5→3, продажа 2 шт., корзина пуста.')
    s.call(res.url)


@case('FR-12, FR-14', 'Высокий', 'Заказы / Карта', 'Повторная оплата оплаченного заказа',
      'Карточный заказ с двумя деталями, остаток после оплаты 3.',
      ['Создать и оплатить заказ.', 'Повторно отправить действие оплаты.', 'Проверить остаток и продажи.'],
      'Появляется ошибка, склад и продажи не меняются.')
def repeated_payment(s):
    u = s.login()
    p = part('repeat')
    cart(s, p)
    checkout(s, u)
    o = latest(u)
    res = s.call(f'/orders/{o.pk}/pay/', {}, follow=True)
    require('Оплатить можно только заказ' in res.content.decode() and stock(p) == 3
            and Sale.objects.filter(part=p).count() == 1, 'Повторный платёж не был корректно отклонён.')


@case('FR-13', 'Высокий', 'Заказы / Отложенная оплата', 'ЕРИП и счёт с оплатой из профиля',
      'Два заказа, для каждого отдельная деталь с остатком 5, количество 2.',
      ['Оформить ЕРИП и счёт.', 'Проверить статус new и отсутствие списания.', 'Оплатить каждый из профиля.'],
      'До оплаты new, 5 шт. и нет продаж; после оплаты paid, 3 шт. и одна продажа.')
def deferred(s):
    u = s.login()
    for method in ['erip', 'invoice']:
        p = part(f'deferred-{method}')
        cart(s, p)
        checkout(s, u, payment_method=method)
        o = latest(u)
        require(o.status == 'new' and not o.paid_at and stock(p) == 5
                and not Sale.objects.filter(part=p).exists(), f'{method}: списание произошло до оплаты.')
        s.call('/profile/')
        s.call(f'/orders/{o.pk}/pay/', {}, follow=True)
        o.refresh_from_db()
        require(o.status == 'paid' and o.paid_at and stock(p) == 3
                and Sale.objects.filter(part=p, quantity=2).count() == 1, f'{method}: оплата не списала товар.')
        s.observe(f'{method}: new (5 шт.) → paid (3 шт.).')


@case('FR-13, NFR-03', 'Высокий', 'Заказы / Отложенная оплата', 'Нехватка одного из двух товаров',
      'В заказе по 2 шт. двух деталей. Остаток второй снижается до 1.',
      ['Оформить ЕРИП.', 'Снизить остаток второй детали.', 'Оплатить и проверить обе позиции и продажи.'],
      'Оплата отклонена, заказ остаётся new. Остатки 5 и 1 сохранены, продаж нет.')
def low_stock(s):
    u = s.login()
    a, b = part('atomic-good'), part('atomic-low')
    cart(s, a)
    cart(s, b)
    checkout(s, u, payment_method='erip')
    o = latest(u)
    Part.objects.filter(pk=b.pk).update(quantity=1)
    res = s.call(f'/orders/{o.pk}/pay/', {}, follow=True)
    o.refresh_from_db()
    require('недостаточно товара' in res.content.decode() and o.status == 'new'
            and stock(a) == 5 and stock(b) == 1 and not Sale.objects.filter(part__in=[a, b]).exists(),
            'Ожидалось атомарное отклонение всего заказа.')


@case('FR-13', 'Высокий', 'Заказы / Отложенная оплата', 'Заголовок подтверждения для заказа new',
      'Неоплаченный заказ ЕРИП.',
      ['Оформить заказ ЕРИП.', 'Из профиля открыть страницу номера заказа.', 'Сверить заголовок и статус.'],
      'Подтверждение показывает, что заказ ожидает оплаты.', 'BUG-5')
def pending_title(s):
    u = s.login()
    cart(s, part('new-title'))
    checkout(s, u, payment_method='erip')
    o = latest(u)
    require(o.status == 'new', 'Не удалось подготовить неоплаченный заказ.')
    s.call('/profile/')
    res = s.call(o.get_absolute_url())
    s.observe(f'Статус БД new; заголовок «Заказ {o.number} оплачен».')
    require(f'{o.number}</span> оплачен' not in res.content.decode(), 'Неоплаченный заказ подписан «оплачен».')


@case('FR-14', 'Высокий', 'Заказы / Отмена', 'Отмена и запрещённые повторные переходы',
      'Один заказ new и один paid у клиента.',
      ['Отменить new.', 'Попробовать повторную отмену и оплату canceled.', 'Попробовать отменить paid.'],
      'new → canceled. Оба терминальных состояния сохраняются.')
def cancel(s):
    u = s.login()
    cart(s, part('cancel'))
    checkout(s, u, payment_method='invoice')
    o = latest(u)
    s.call(f'/orders/{o.pk}/cancel/', {}, follow=True)
    o.refresh_from_db()
    require(o.status == 'canceled', 'Отмена не выполнена.')
    for action in ['cancel', 'pay']:
        res = s.call(f'/orders/{o.pk}/{action}/', {}, follow=True)
        require('можно только заказ' in res.content.decode(), f'Повторное действие {action} не отклонено.')
    cart(s, part('cancel-paid'))
    checkout(s, u)
    paid = latest(u)
    res = s.call(f'/orders/{paid.pk}/cancel/', {}, follow=True)
    o.refresh_from_db()
    paid.refresh_from_db()
    require('Отменить можно только заказ' in res.content.decode()
            and o.status == 'canceled' and paid.status == 'paid', 'Терминальное состояние изменилось.')


@case('FR-15', 'Высокий', 'Заказы / Права владельца', 'Свой заказ доступен, чужой изолирован',
      'Клиенты QA A/B, по одному собственному заказу new.',
      ['Войти как A и открыть своё подтверждение.', 'В той же сессии запросить подтверждение заказа B и проверить запрет оплаты/отмены.',
       'Сверить статус заказа B.'],
      'Свой GET → 200; чужие GET и POST → 404, заказ B остаётся new.')
def owner(s):
    a = s.login()
    cart(s, part('owner-a'))
    checkout(s, a, payment_method='erip')
    oa = latest(a)
    actor = s.client
    s.client = Client(raise_request_exception=False)
    b = s.login('qa_owner_b')
    cart(s, part('owner-b'))
    checkout(s, b, payment_method='erip')
    ob = latest(b)
    s.client = actor
    require(s.call(oa.get_absolute_url()).status_code == 200, 'Своё подтверждение закрыто.')
    for action in ['pay', 'cancel']:
        require(s.call(f'/orders/{ob.pk}/{action}/', {}).status_code == 404, 'Операция для чужого заказа разрешена.')
    require(s.call(ob.get_absolute_url()).status_code == 404, 'Чужое подтверждение доступно.')
    ob.refresh_from_db()
    require(ob.status == 'new', 'Чужой заказ изменил состояние.')


@case('FR-16, NFR-02', 'Высокий', 'Аккаунт / Регистрация', 'Регистрация совершеннолетнего',
      'Уникальные username/email, дата 1990-01-01, телефон РБ.',
      ['Отправить форму.', 'Открыть профиль.', 'Проверить запись профиля и хеш пароля.'],
      'Созданы пользователь и профиль, вход выполнен, пароль хранится в виде хеша.')
def register_ok(s):
    r = s.call('/register/', registration(), follow=True)
    u = User.objects.filter(username='qa_reg').first()
    require(r.redirect_chain == [('/profile/', 302)] and u is not None and u.password != PASSWORD
            and u.check_password(PASSWORD) and BuyerProfile.objects.filter(user=u, phone=PHONE).exists(),
            'Аккаунт, профиль или пароль не прошёл проверку.')
    s.observe('Аккаунт и профиль сохранены, check_password=True, открытый пароль отсутствует.')


@case('FR-16', 'Высокий', 'Аккаунт / Регистрация', 'Возраст, повторный email и некорректный телефон',
      'Существующий qa_existing@example.test, дата рождения сегодня, телефон 12345.',
      ['Создать исходного клиента.', 'Зарегистрировать второго с указанными данными.', 'Проверить три ошибки и отсутствие записи.'],
      'Ошибки email, даты и телефона, новый аккаунт отсутствует.')
def register_invalid(s):
    existing = buyer('qa_existing')
    r = s.call('/register/', registration(email=existing.email, birth_date=str(TODAY), phone='12345'))
    require({'email', 'birth_date', 'phone'} <= set(r.context['form'].errors)
            and not User.objects.filter(username='qa_reg').exists(), 'Некорректная регистрация принята.')


@case('FR-17', 'Средний', 'Отзывы', 'Гость, допустимая и запредельная оценки',
      'QA покупатель, текст «Хороший тестовый магазин.», оценки 5, 0, 6.',
      ['Открыть форму гостем.', 'Войти и отправить оценки 0 и 6.', 'Отправить оценку 5.'],
      'Гость направлен на вход, 0/6 отклонены, отзыв на 5 сохранён и виден.')
def reviews(s):
    require(s.call('/reviews/add/').url.startswith('/login/'), 'Гостю доступна форма отзыва.')
    u = s.login()
    for rating in [0, 6]:
        r = s.call('/reviews/add/', {'rating': rating, 'text': 'Хороший тестовый магазин.'})
        require('rating' in r.context['form'].errors, f'Оценка {rating} принята.')
    r = s.call('/reviews/add/', {'rating': 5, 'text': 'Хороший тестовый магазин.'}, follow=True)
    require(Review.objects.filter(user=u, rating=5).count() == 1
            and 'Хороший тестовый магазин.' in r.content.decode(), 'Отзыв 5 недоступен.')


@case('FR-18', 'Высокий', 'Управление / Товары', 'Создание, редактирование и мягкое удаление',
      'Сотрудник и контрольные тип/изготовитель; цена 20→30 BYN.',
      ['Создать товар QA-CRUD.', 'Изменить цену.', 'Удалить через подтверждение и проверить каталог и БД.'],
      'Цена 30 BYN сохранена, is_active=False и запись в БД остаётся.')
def staff_crud(s):
    s.login('qa_crud_staff', profile=False, staff=True)
    base = part('crud-fixture')
    data = dict(sku='QA-CRUD', name='QA Товар для CRUD', product_type=base.product_type_id,
                manufacturer=base.manufacturer_id, price='20.00', quantity=2, description='Деталь для QA', is_active='on')
    r = s.call('/parts/create/', data)
    p = Part.objects.filter(sku='QA-CRUD').first()
    require(r.status_code == 302 and p is not None, 'Товар не создан.')
    data['price'] = '30.00'
    s.call(f'/parts/{p.pk}/edit/', data)
    p.refresh_from_db()
    require(p.price == 30, 'Цена не изменена.')
    s.call(f'/parts/{p.pk}/delete/', {}, follow=True)
    p.refresh_from_db()
    require(not p.is_active and p.name not in names(s.call('/parts/?q=CRUD')), 'Товар не скрыт.')


@case('FR-18, FR-19', 'Высокий', 'Управление / Доступ', 'Клиенту запрещены каталог и статистика сотрудника',
      'Клиент и одна активная деталь.',
      ['Отправить запросы создания, редактирования и удаления товара как клиент.', 'Открыть статистику и график.', 'Проверить исходную запись.'],
      'Все закрытые маршруты перенаправляют на вход; деталь остаётся активной.')
def staff_denied(s):
    s.login()
    p = part('staff-denied')
    for url, data in [('/parts/create/', {}), (f'/parts/{p.pk}/edit/', {}), (f'/parts/{p.pk}/delete/', {}),
                      ('/stats/', None), ('/stats/chart.png', None)]:
        r = s.call(url, data)
        require(r.status_code == 302 and r.url.startswith('/login/'), f'Клиенту доступен {url}.')
    p.refresh_from_db()
    require(p.is_active, 'Неавторизованное изменение товара.')
    s.call('/stats/', follow=True)


@case('FR-19', 'Средний', 'Управление / Статистика', 'Числа продаж и изображение графика',
      'Две продажи по 50 BYN и одна 100 BYN, один тип товара. Изолированный набор продаж.',
      ['Убрать демопродажи внутри откатываемой транзакции.', 'Создать контрольные продажи.', 'Войти сотрудником и открыть статистику и график.'],
      'Сумма 200, среднее 66,67, медиана и мода 50, тип «Контрольные фильтры», PNG → 200.')
def stats(s):
    Sale.objects.all().delete()
    u = buyer('qa_stats_buyer')
    p = part('stats', quantity=15)
    for cost in [50, 50, 100]:
        Sale.objects.create(client=u.client_profile, part=p, quantity=1, unit_price=Decimal(cost))
    s.login('qa_stats_staff', profile=False, staff=True)
    chart = s.call('/stats/chart.png')
    r = s.call('/stats/')
    v = r.context['stat_values']
    s.observe(f'Числа: {v}. График: {chart.headers.get("Content-Type")}.')
    require(v['total_sum'] == 200 and round(v['average'], 2) == Decimal('66.67') and v['median'] == 50
            and v['mode'] == 50 and v['top_type'] == p.product_type.name and chart.content.startswith(b'\x89PNG'),
            'Показатели или график отличаются от контрольных.')


@case('FR-20', 'Высокий', 'API / Каталог', 'JSON с разграничением SKU',
      'Позиция 100.00 BYN / 5 шт. и скрытая позиция. Гость, клиент, сотрудник.',
      ['Запросить JSON гостем.', 'Повторить клиентом.', 'Повторить сотрудником и сравнить схему и значения.'],
      'Гость → вход. Клиент видит name/price/quantity, сотрудник также sku. Скрытая деталь отсутствует.')
def api_parts(s):
    p = part('json', 'QA JSON')
    hidden = part('api-hidden', is_active=False)
    require(s.call('/api/parts/').url.startswith('/login/'), 'Гостю выдан JSON каталога.')
    s.login()
    r = s.call('/api/parts/')
    row = next(x for x in r.json()['results'] if x['name'] == p.name)
    require(row == {'name': p.name, 'price': '100.00', 'quantity': 5}
            and all(x['name'] != hidden.name for x in r.json()['results']), 'Клиентский JSON неверен.')
    s.login('qa_api_case_staff', profile=False, staff=True)
    row = next(x for x in s.call('/api/parts/').json()['results'] if x['name'] == p.name)
    require(row == {'sku': p.sku, 'name': p.name, 'price': '100.00', 'quantity': 5}, 'JSON сотрудника неверен.')


@case('FR-21, NFR-03', 'Средний', 'Интеграции', 'Факт и IP при успешном ответе сервисов',
      'Заглушки Cat Facts и IPify: «QA cat fact.» и 192.0.2.10.',
      ['Подменить внешние HTTP-ответы.', 'Открыть страницу.', 'Проверить оба значения.'],
      'HTTP 200, факт и IP совпадают с данными заглушек.')
def external_ok(s):
    with responses.RequestsMock() as stub:
        stub.get('https://catfact.ninja/fact', json={'fact': 'QA cat fact.'})
        stub.get('https://api.ipify.org?format=json', json={'ip': '192.0.2.10'})
        res = s.call('/external-apis/')
        text = res.content.decode()
        require(res.status_code == 200 and 'QA cat fact.' in text and '192.0.2.10' in text,
                'Страница не отобразила оба контрольных значения.')


@case('FR-21, NFR-03', 'Средний', 'Интеграции', 'Таймаут и серверная ошибка поставщика',
      'Cat Facts → Timeout, IPify → HTTP 503.',
      ['Задать два отказа на HTTP-границе.', 'Открыть интеграции.', 'Проверить запасные тексты и заголовок страницы.'],
      'HTTP 200, для каждого сервиса есть запасное значение.')
def external_fail(s):
    with responses.RequestsMock() as stub:
        stub.get('https://catfact.ninja/fact', body=Timeout('synthetic timeout'))
        stub.get('https://api.ipify.org?format=json', status=503)
        res = s.call('/external-apis/')
        text = res.content.decode()
        require(res.status_code == 200 and 'API временно недоступен' in text
                and 'не удалось получить' in text, 'Не показан запасной текст.')


@case('FR-22', 'Средний', 'Контакты / Валидация', 'Ошибки заявки и граничные длины сообщения',
      'Имя из 1 символа, email bad, телефон 12, VIN пустой либо 16 символов, сообщение 9/601, год 1979.',
      ['Отправить некорректную форму.', 'Повторить для двух длин сообщения и разных VIN.',
       'Проверить ошибки и отсутствие подтверждения.'],
      'Ошибка у каждого некорректного поля, заявка не принята.')
def feedback_invalid(s):
    for message, vin in [('x' * 9, ''), ('x' * 601, 'WVWZZZ1KZAW00000')]:
        res = s.call('/contacts/', feedback(name='И', email='bad', phone='12', message=message,
                                             vin=vin, production_year=1979))
        errors = set(res.context['form'].errors)
        require({'name', 'email', 'phone', 'vin', 'message', 'production_year'} <= errors,
                f'Пропущены ошибки, набор фактических ошибок {errors}.')


@case('FR-22', 'Средний', 'Контакты / Валидация', 'Следующий модельный год',
      'Корректная заявка, год на единицу больше текущего.',
      ['Заполнить валидные поля, указать следующий год.', 'Отправить заявку.'],
      'Разрешённый год принят, форма перенаправляет после сохранения.', 'BUG-6')
def feedback_year(s):
    res = s.call('/contacts/', feedback(production_year=TODAY.year + 1))
    require(res.status_code == 302, f'Год {TODAY.year + 1} отклонён: {res.context["form"].errors.get_json_data().get("production_year")}.')


@case('FR-22', 'Средний', 'Контакты / Хранение', 'Менеджеру доступна отправленная заявка',
      'Валидные данные и тег QA-REQUEST в тексте.',
      ['Отправить заявку.', 'Проверить подтверждение и журнал.', 'Проверить обработчик и список моделей администратора.'],
      'Менеджер может открыть сохранённый текст заявки после отправки.', 'BUG-7')
def feedback_store(s):
    capture = io.StringIO()
    handler = logging.StreamHandler(capture)
    log = logging.getLogger('shop.views')
    log.addHandler(handler)
    try:
        r = s.call('/contacts/', feedback(message='QA-REQUEST: нужен масляный фильтр.'), follow=True)
    finally:
        log.removeHandler(handler)
    require('Заявка отправлена' in r.content.decode(), 'Форма не приняла исходные данные.')
    from django.apps import apps
    from django.contrib import admin
    import inspect
    from shop.views import contacts
    models = [m.__name__ for m in apps.get_app_config('shop').get_models()]
    admin_models = [m.__name__ for m in admin.site._registry]
    s.observe(f'Журнал: {capture.getvalue().strip()}. Обработчик только пишет email и тему, затем перенаправляет.')
    s.observe(f'Модели магазина: {", ".join(models)}; разделы админки: {", ".join(admin_models)}.')
    accepted_branch = inspect.getsource(contacts).split('if form.is_valid():', 1)[1].split('    else:', 1)[0]
    require(not ('logger.info' in accepted_branch and '.save(' not in accepted_branch
                 and 'QA-REQUEST' not in capture.getvalue() and 'Feedback' not in admin_models),
            'Пользователь видит подтверждение, но сохраняемой записи для менеджера нет.')


def run(destination):
    require_scratch_database()
    setup_test_environment()
    bodies = destination / 'responses'
    bodies.mkdir(parents=True, exist_ok=True)
    results = []
    for metadata, scenario in CASES:
        s = Scenario()
        record = dict(metadata)
        with transaction.atomic(), override_settings(DEBUG=False):
            try:
                scenario(s)
            except AssertionError as error:
                record.update(status='FAIL', result=str(error))
            except Exception as error:
                record.update(status='ERROR', result=f'{type(error).__name__}: {error}')
            else:
                record.update(status='PASS', result='Проверки совпали с ожидаемым результатом.')
            if s.last is not None:
                response = s.last
                mime = response.headers.get('Content-Type', '')
                if 'text/html' in mime or 'application/json' in mime:
                    suffix = '.html' if 'text/html' in mime else '.json'
                    filename = record['id'] + suffix
                    (bodies / filename).write_bytes(response.content)
                    record['body'] = filename
            transaction.set_rollback(True)
        record['observations'] = s.notes
        results.append(record)
        print(record['id'], record['status'], record['result'], flush=True)
    (destination / 'system-results.json').write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding='utf-8')

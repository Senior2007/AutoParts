# Тестирование (ЛР2)

Инструменты: `pytest` + `pytest-django` (запуск, фикстуры, чистая БД на каждый тест), `unittest.mock` (моки),
`responses` (заглушки HTTP-запросов), `pytest-cov` (покрытие), `pytest-randomly` (случайный порядок запуска).

## Структура `shop/tests/`

| Файл | Вид | Кол-во | Что проверяет |
| --- | --- | --- | --- |
| `conftest.py` | — | — | общие фикстуры: товар, покупатель, сотрудник, промокод, данные формы заказа |
| `test_unit.py` | модульные | 72 | `Cart` (сессия и `Part.objects` — моки), валидаторы, свойства моделей, `Order.pay/cancel` (`save` — мок), `CheckoutForm`, `_safe_api_get` (`requests.get` — мок), `format_utc_offset` |
| `test_integration.py` | интеграционные | 31 | модели + БД (списание остатка, оплата заказа), формы + БД (регистрация), представления + БД (поиск, сортировка, права), внешние API через заглушки `responses` |
| `test_scenarios.py` | сценарные | 15 | цепочки HTTP-запросов по диаграмме состояний заказа: корзина → `new` → `paid` / `canceled`, запрещенные переходы |
| `test_defects.py` | регрессионные | 6 (xfail) | дефекты из `ISSUES.md`; падают, пока дефект не исправлен |
| `test_regression.py` | регрессионные | 76 | ранее написанные тесты проекта (страницы, корзина, оформление заказа, формы) |

## Требования к тестам и где они выполнены

| Требование | Как выполнено |
| --- | --- |
| Arrange–Act–Assert, понятные имена | блоки помечены комментариями `# Arrange / # Act / # Assert`; имена вида `test_<что>_<ожидаемый результат>` |
| Параметризация | `@pytest.mark.parametrize`: лимиты корзины (7 наборов), телефоны, email, возраст, промокоды, ошибки формы заказа (10 наборов), поиск, сортировка, права, сбои API, запрещенные переходы |
| Негативные тесты | неверный телефон/email/карта/CVC, дата в прошлом, младше 18, занятый email, количество 0 и −3, больше остатка, повторная оплата, отмена оплаченного, чужой заказ (404), GET вместо POST (405), сбой внешнего API |
| Граничные случаи | ровно 18 лет / на день меньше, 99 шт. в корзине, промокод на один день, весь остаток |
| Независимость | каждая функция получает чистую БД (транзакция откатывается), данные создаются фикстурами; `pytest-randomly` запускает тесты в случайном порядке |
| Моки в юнит-тестах | `patch('shop.cart.Part')`, `patch.object(Order, 'save')`, `patch('shop.views.requests.get')`, `patch('shop.models.timezone.localdate')` |
| Заглушки HTTP в интеграционных | `@responses.activate` + `responses.get(URL, json=... / status=500 / body=ConnectionError)` |

## Запуск

```bash
.venv/bin/python -m pytest
```

```bash
.venv/bin/python -m pytest --cov --cov-report=term-missing --cov-report=html
```

Только один вид тестов:

```bash
.venv/bin/python -m pytest shop/tests/test_scenarios.py -v
```

## Покрытие

Исключено из подсчета (`.coveragerc`): `shop/migrations/`, `config/` (настройки), `manage.py`,
`shop/management/` (скрипт заполнения демо-данными), сами тесты.

| Набор | Покрытие |
| --- | --- |
| Все тесты | **94%** |
| Только новые тесты ЛР2 (`test_unit`, `test_integration`, `test_scenarios`, `test_defects`) | **76%** |

```
Name                         Stmts   Miss  Cover
------------------------------------------------
shop/admin.py                   69      0   100%
shop/cart.py                    53      1    98%
shop/context_processors.py       5      0   100%
shop/forms.py                  221      6    97%
shop/models.py                 359     19    95%
shop/timeinfo.py                22      1    95%
shop/urls.py                     4      0   100%
shop/views.py                  374     35    91%
------------------------------------------------
TOTAL                         1110     62    94%
```

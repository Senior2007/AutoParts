from datetime import date, timedelta
from decimal import Decimal
from unittest.mock import patch

from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.utils import timezone
from django.test import TestCase
from django.urls import reverse

from shop.forms import CheckoutForm, FeedbackForm, RegistrationForm
from shop.models import (
    Client,
    CompanyInfo,
    CompanyProfile,
    Employee,
    Manufacturer,
    NewsArticle,
    Order,
    OrderItem,
    Part,
    Partner,
    ProductType,
    PromoCode,
    Review,
    Sale,
    Supplier,
    Supply,
    Term,
    Vacancy,
    validate_adult,
)


class ValidationTests(TestCase):
    def test_validate_adult_rejects_underage(self):
        with self.assertRaises(ValidationError):
            validate_adult(date.today().replace(year=date.today().year - 17))

    def test_registration_form_rejects_wrong_phone(self):
        form = RegistrationForm(
            data={
                'username': 'new_client',
                'first_name': 'Иван',
                'last_name': 'Петров',
                'birth_date': '1999-01-01',
                'phone': '80291234567',
                'email': 'client@example.com',
                'address': 'Минск',
                'password1': 'StrongPass12345',
                'password2': 'StrongPass12345',
            }
        )
        self.assertFalse(form.is_valid())
        self.assertIn('phone', form.errors)

    def test_registration_form_rejects_invalid_email(self):
        form = RegistrationForm(
            data={
                'username': 'new_client2',
                'first_name': 'Иван',
                'last_name': 'Петров',
                'birth_date': '1999-01-01',
                'phone': '+375 (29) 123-45-67',
                'email': 'not-an-email',
                'address': 'Минск',
                'password1': 'StrongPass12345',
                'password2': 'StrongPass12345',
            }
        )
        self.assertFalse(form.is_valid())
        self.assertIn('email', form.errors)


class ShopViewTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user('client', password='client12345')
        self.client_profile = Client.objects.create(
            user=self.user,
            first_name='Иван',
            last_name='Петров',
            birth_date=date(1990, 1, 1),
            phone='+375 (29) 123-45-67',
            email='client@example.com',
            address='Минск',
        )
        self.product_type = ProductType.objects.create(name='Фильтры')
        self.manufacturer = Manufacturer.objects.create(name='Parts Co', country='Germany')
        self.supplier = Supplier.objects.create(
            name='Поставщик',
            address='Минск',
            phone='+375 (33) 123-45-67',
            email='supplier@example.com',
        )
        self.part = Part.objects.create(
            sku='T-1',
            name='Фильтр',
            product_type=self.product_type,
            manufacturer=self.manufacturer,
            price=Decimal('50.00'),
            quantity=5,
            description='Тестовая запчасть',
        )
        self.employee = Employee.objects.create(
            first_name='Анна',
            last_name='Смирнова',
            position='Менеджер',
            birth_date=date(1990, 1, 1),
            phone='+375 (44) 111-22-33',
            email='employee@example.com',
            responsibilities='Консультации клиентов.',
        )
        CompanyInfo.objects.create(title='Открытие', content='История компании.', year=2020)
        NewsArticle.objects.create(
            title='Поступили новые фильтры',
            slug='new-filters',
            summary='Краткая новость о поставке.',
            content='Полный текст новости.',
            published_at=timezone.now(),
        )
        Term.objects.create(title='Артикул', definition='Уникальный код товара.')
        Vacancy.objects.create(title='Менеджер', description='Работа с заказами.', salary_min=1000, salary_max=1500)
        Review.objects.create(user=self.user, name='Иван Петров', rating=5, text='Хороший магазин и быстрый подбор.')
        promo = PromoCode.objects.create(
            code='TEST10',
            description='Тестовая скидка.',
            discount_percent=10,
            starts_at=date(2026, 1, 1),
            ends_at=date(2026, 12, 31),
        )
        promo.product_types.add(self.product_type)

    def test_public_parts_page_available(self):
        response = self.client.get(reverse('part_list'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Фильтр')

    def test_api_requires_login(self):
        response = self.client.get(reverse('parts_api'))
        self.assertEqual(response.status_code, 302)

    def test_logged_user_can_buy_part(self):
        self.client.login(username='client', password='client12345')
        response = self.client.post(reverse('sale_create'), {'part': self.part.pk, 'quantity': 2})
        self.assertEqual(response.status_code, 302)
        self.assertEqual(Sale.objects.count(), 1)
        self.part.refresh_from_db()
        self.assertEqual(self.part.quantity, 3)

    def test_user_without_client_redirected_to_complete_profile_on_buy(self):
        orphan = User.objects.create_user('orphan', password='orphan12345', first_name='О', last_name='Сиротин')
        self.client.login(username='orphan', password='orphan12345')
        response = self.client.get(reverse('sale_create'))
        self.assertRedirects(response, reverse('complete_client_profile'))

    def test_complete_client_profile_allows_purchase(self):
        orphan = User.objects.create_user('buyer2', password='buyer12345', email='buyer2@example.com')
        self.client.login(username='buyer2', password='buyer12345')
        response = self.client.post(
            reverse('complete_client_profile'),
            {
                'first_name': 'Покупатель',
                'last_name': 'Новый',
                'birth_date': '1995-06-06',
                'phone': '+375 (29) 888-77-66',
                'email': 'buyer2@example.com',
                'address': 'Минск',
            },
        )
        self.assertRedirects(response, reverse('profile'))
        self.assertTrue(Client.objects.filter(user__username='buyer2').exists())
        response = self.client.post(reverse('sale_create'), {'part': self.part.pk, 'quantity': 1})
        self.assertEqual(response.status_code, 302)

    def test_registration_post_succeeds_with_csrf(self):
        session = self.client.session
        session.save()
        response = self.client.get(reverse('register'))
        self.assertEqual(response.status_code, 200)
        response = self.client.post(
            reverse('register'),
            {
                'username': 'newbuyer',
                'first_name': 'Новый',
                'last_name': 'Покупатель',
                'birth_date': '1995-05-05',
                'phone': '+375 (29) 555-66-77',
                'email': 'newbuyer@example.com',
                'address': 'Минск',
                'password1': 'StrongPass12345',
                'password2': 'StrongPass12345',
            },
        )
        self.assertEqual(response.status_code, 302)
        self.assertTrue(Client.objects.filter(user__username='newbuyer').exists())

    def test_sale_with_valid_promo_applies_discount(self):
        self.client.login(username='client', password='client12345')
        response = self.client.post(
            reverse('sale_create'),
            {'part': self.part.pk, 'quantity': 1, 'promo_code': 'TEST10'},
        )
        self.assertEqual(response.status_code, 302)
        sale = Sale.objects.latest('sold_at')
        self.assertEqual(sale.unit_price, Decimal('45.00'))

    def test_sale_rejects_promo_for_wrong_product_type(self):
        brakes_type = ProductType.objects.create(name='Тормозная система')
        promo = PromoCode.objects.create(
            code='BRAKEONLY',
            description='Только тормоза.',
            discount_percent=10,
            starts_at=date(2026, 1, 1),
            ends_at=date(2026, 12, 31),
        )
        promo.product_types.add(brakes_type)
        self.client.login(username='client', password='client12345')
        response = self.client.post(
            reverse('sale_create'),
            {'part': self.part.pk, 'quantity': 1, 'promo_code': 'BRAKEONLY'},
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(Sale.objects.count(), 0)
        self.assertContains(response, 'не действует для типа')

    def test_staff_crud_is_forbidden_for_regular_user(self):
        self.client.login(username='client', password='client12345')
        response = self.client.get(reverse('part_create'))
        self.assertEqual(response.status_code, 302)

    def test_staff_can_soft_delete_part(self):
        staff = User.objects.create_user('staff', password='staff12345', is_staff=True)
        self.client.force_login(staff)
        response = self.client.post(reverse('part_delete', args=[self.part.pk]))
        self.assertEqual(response.status_code, 302)
        self.part.refresh_from_db()
        self.assertFalse(self.part.is_active)

    def test_required_public_pages_are_available(self):
        url_names = [
            'home',
            'about',
            'news_list',
            'terms',
            'contacts',
            'privacy',
            'vacancies',
            'reviews',
        ]
        for name in url_names:
            with self.subTest(name=name):
                response = self.client.get(reverse(name))
                self.assertEqual(response.status_code, 200)

    def test_employees_page_and_api_are_available(self):
        self.assertEqual(self.client.get(reverse('employees')).status_code, 200)
        data = self.client.get(reverse('employees_api')).json()['results']
        self.assertEqual(len(data), 1)
        self.assertEqual(data[0]['full_name'], 'Смирнова Анна')
        self.assertEqual(data[0]['description'], 'Менеджер. Консультации клиентов.')
        self.assertEqual(data[0]['phone'], '+375 (44) 111-22-33')

    def test_js_tasks_page_is_available(self):
        response = self.client.get(reverse('js_tasks'))
        self.assertContains(response, 'id="file-field-add"')
        self.assertContains(response, 'id="cos-chart"')

    def test_promos_require_login(self):
        self.assertEqual(self.client.get(reverse('promos')).status_code, 302)
        self.client.login(username='client', password='client12345')
        self.assertEqual(self.client.get(reverse('promos')).status_code, 200)

    def test_part_list_filter_by_type(self):
        optics = ProductType.objects.create(name='Оптика')
        Part.objects.create(
            sku='T-OPT',
            name='Фара',
            product_type=optics,
            manufacturer=self.manufacturer,
            price=Decimal('100.00'),
            quantity=3,
            description='Тестовая оптика',
        )
        response = self.client.get(reverse('part_list'), {'type': optics.pk})
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Фара')
        self.assertNotContains(response, f'href="{self.part.get_absolute_url()}"')

    def test_part_list_search_without_javascript(self):
        response = self.client.get(reverse('part_list'), {'q': 'Фильтр'})
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Фильтр')
        self.assertNotContains(response, '<script>')

    def test_part_list_sort_by_price(self):
        cheap = Part.objects.create(
            sku='T-CHEAP',
            name='Дешевый',
            product_type=self.product_type,
            manufacturer=self.manufacturer,
            price=Decimal('10.00'),
            quantity=1,
            description='Дешевый товар',
        )
        expensive = Part.objects.create(
            sku='T-EXP',
            name='Дорогой',
            product_type=self.product_type,
            manufacturer=self.manufacturer,
            price=Decimal('999.00'),
            quantity=1,
            description='Дорогой товар',
        )
        response = self.client.get(reverse('part_list'), {'sort': 'price'})
        self.assertEqual(response.status_code, 200)
        content = response.content.decode()
        self.assertLess(content.index('Дешевый'), content.index('Дорогой'))
        response = self.client.get(reverse('part_list'), {'sort': 'price_desc'})
        content = response.content.decode()
        self.assertLess(content.index('Дорогой'), content.index('Дешевый'))

    def test_sku_hidden_for_regular_user(self):
        response = self.client.get(reverse('part_list'))
        self.assertNotContains(response, 'T-1')
        self.assertNotContains(response, '>Артикул<')
        response = self.client.get(reverse('part_detail', args=[self.part.pk]))
        self.assertNotContains(response, 'T-1')

    def test_sku_visible_for_staff(self):
        staff = User.objects.create_user('staff2', password='staff12345', is_staff=True)
        self.client.force_login(staff)
        response = self.client.get(reverse('part_list'))
        self.assertContains(response, 'T-1')
        self.assertContains(response, 'Артикул')

    def test_suppliers_hidden_for_regular_user(self):
        Supply.objects.create(
            supplier=self.supplier,
            part=self.part,
            quantity=10,
            unit_price=Decimal('30.00'),
        )
        response = self.client.get(reverse('part_detail', args=[self.part.pk]))
        self.assertNotContains(response, 'Поставщик')
        self.assertNotContains(response, '>Поставщики<')
        response = self.client.get(reverse('home'))
        self.assertNotContains(response, 'поставщиков')

    def test_suppliers_visible_for_staff(self):
        Supply.objects.create(
            supplier=self.supplier,
            part=self.part,
            quantity=10,
            unit_price=Decimal('30.00'),
        )
        staff = User.objects.create_user('staff3', password='staff12345', is_staff=True)
        self.client.force_login(staff)
        response = self.client.get(reverse('part_detail', args=[self.part.pk]))
        self.assertContains(response, 'Поставщик')
        self.assertContains(response, 'Поставщики')
        response = self.client.get(reverse('home'))
        self.assertContains(response, 'поставщиков')

    def test_news_detail_and_part_detail_are_available(self):
        self.assertEqual(self.client.get(reverse('news_detail', args=['new-filters'])).status_code, 200)
        self.assertEqual(self.client.get(reverse('part_detail', args=[self.part.pk])).status_code, 200)

    def test_review_create_requires_login_and_saves_for_user(self):
        self.assertEqual(self.client.get(reverse('review_create')).status_code, 302)
        self.client.login(username='client', password='client12345')
        response = self.client.post(reverse('review_create'), {'rating': 5, 'text': 'Очень помогли с подбором детали.'})
        self.assertEqual(response.status_code, 302)
        self.assertTrue(Review.objects.filter(text='Очень помогли с подбором детали.').exists())

    @patch('shop.views._safe_api_get')
    def test_external_api_page_uses_two_values(self, mocked_api):
        mocked_api.side_effect = [{'fact': 'Fact'}, {'ip': '127.0.0.1'}]
        response = self.client.get(reverse('external_apis'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Fact')
        self.assertContains(response, '127.0.0.1')

    def test_stats_and_chart_for_staff_only(self):
        Sale.objects.create(client=self.client_profile, part=self.part, employee=self.employee, quantity=1, unit_price=self.part.price)
        self.client.login(username='client', password='client12345')
        self.assertEqual(self.client.get(reverse('stats')).status_code, 302)
        self.assertEqual(self.client.get(reverse('sales_chart')).status_code, 302)

        staff = User.objects.create_user('stats_staff', password='staff12345', is_staff=True)
        self.client.force_login(staff)
        self.assertEqual(self.client.get(reverse('stats')).status_code, 200)
        chart = self.client.get(reverse('sales_chart'))
        self.assertEqual(chart.status_code, 200)
        self.assertEqual(chart['Content-Type'], 'image/png')


class ResponsiveImageTests(TestCase):
    def setUp(self):
        self.product_type = ProductType.objects.create(name='Фильтры')
        self.manufacturer = Manufacturer.objects.create(name='Parts Co', country='Germany')

    def make_part(self, image_url):
        return Part.objects.create(
            sku=f'R-{Part.objects.count()}',
            name='Фильтр',
            product_type=self.product_type,
            manufacturer=self.manufacturer,
            price=Decimal('10.00'),
            quantity=1,
            description='Товар',
            image_url=image_url,
        )

    def test_srcset_is_built_for_resizable_image(self):
        part = self.make_part('https://images.unsplash.com/photo-1?auto=format&w=900&q=80')
        self.assertEqual(
            part.image_srcset,
            'https://images.unsplash.com/photo-1?auto=format&w=480&q=80 480w, '
            'https://images.unsplash.com/photo-1?auto=format&w=900&q=80 900w, '
            'https://images.unsplash.com/photo-1?auto=format&w=1600&q=80 1600w',
        )

    def test_srcset_is_empty_for_plain_image(self):
        self.assertEqual(self.make_part('https://example.com/filter.jpg').image_srcset, '')

    def test_home_banners_have_art_direction_and_resolution_switching(self):
        content = self.client.get(reverse('home')).content.decode()
        self.assertEqual(content.count('<picture>'), 3)
        self.assertEqual(content.count('media="(max-width: 480px)"'), 3)
        self.assertIn('banner-brake-portrait-640.jpg', content)
        self.assertIn('banner-brake-1600.jpg 1600w', content)

class CartTests(TestCase):
    def setUp(self):
        self.product_type = ProductType.objects.create(name='Фильтры')
        self.manufacturer = Manufacturer.objects.create(name='Parts Co', country='Germany')
        self.part = Part.objects.create(
            sku='C-1',
            name='Фильтр салона',
            product_type=self.product_type,
            manufacturer=self.manufacturer,
            price=Decimal('40.00'),
            quantity=5,
            description='Товар для корзины',
        )

    def test_empty_cart_page_available(self):
        response = self.client.get(reverse('cart_detail'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Корзина пуста')

    def test_add_part_to_cart(self):
        response = self.client.post(reverse('cart_add', args=[self.part.pk]), {'quantity': 2})
        self.assertRedirects(response, reverse('cart_detail'))
        self.assertEqual(self.client.session['cart'], {str(self.part.pk): 2})

    def test_cart_add_rejects_get_request(self):
        self.assertEqual(self.client.get(reverse('cart_add', args=[self.part.pk])).status_code, 405)

    def test_add_is_limited_by_stock(self):
        self.client.post(reverse('cart_add', args=[self.part.pk]), {'quantity': 99})
        self.assertEqual(self.client.session['cart'][str(self.part.pk)], self.part.quantity)

    def test_out_of_stock_part_is_not_added(self):
        self.part.quantity = 0
        self.part.save()
        response = self.client.post(reverse('cart_add', args=[self.part.pk]), {'quantity': 1})
        self.assertRedirects(response, self.part.get_absolute_url())
        self.assertFalse(self.client.session.get('cart'))

    def test_increase_and_decrease_quantity(self):
        self.client.post(reverse('cart_add', args=[self.part.pk]), {'quantity': 1})
        self.client.post(reverse('cart_update', args=[self.part.pk]), {'action': 'increase'})
        self.assertEqual(self.client.session['cart'][str(self.part.pk)], 2)
        self.client.post(reverse('cart_update', args=[self.part.pk]), {'action': 'decrease'})
        self.assertEqual(self.client.session['cart'][str(self.part.pk)], 1)

    def test_decrease_last_item_removes_it(self):
        self.client.post(reverse('cart_add', args=[self.part.pk]), {'quantity': 1})
        self.client.post(reverse('cart_update', args=[self.part.pk]), {'action': 'decrease'})
        self.assertEqual(self.client.session['cart'], {})

    def test_increase_above_stock_is_blocked(self):
        self.client.post(reverse('cart_add', args=[self.part.pk]), {'quantity': 5})
        self.client.post(reverse('cart_update', args=[self.part.pk]), {'action': 'increase'})
        self.assertEqual(self.client.session['cart'][str(self.part.pk)], 5)

    def test_remove_and_clear_cart(self):
        self.client.post(reverse('cart_add', args=[self.part.pk]), {'quantity': 2})
        self.client.post(reverse('cart_remove', args=[self.part.pk]))
        self.assertEqual(self.client.session['cart'], {})
        self.client.post(reverse('cart_add', args=[self.part.pk]), {'quantity': 2})
        self.client.post(reverse('cart_clear'))
        self.assertEqual(self.client.session['cart'], {})

    def test_deleted_part_is_dropped_from_cart(self):
        self.client.post(reverse('cart_add', args=[self.part.pk]), {'quantity': 2})
        session = self.client.session
        session['cart'] = {str(self.part.pk): 2, '999999': 1}
        session.save()
        self.client.get(reverse('cart_detail'))
        self.assertEqual(self.client.session['cart'], {str(self.part.pk): 2})

    def test_deactivated_part_is_dropped_from_cart(self):
        self.client.post(reverse('cart_add', args=[self.part.pk]), {'quantity': 1})
        self.part.is_active = False
        self.part.save()
        response = self.client.get(reverse('cart_detail'))
        self.assertContains(response, 'Корзина пуста')

    def test_cart_page_shows_total(self):
        self.client.post(reverse('cart_add', args=[self.part.pk]), {'quantity': 3})
        response = self.client.get(reverse('cart_detail'))
        self.assertContains(response, 'Фильтр салона')
        self.assertEqual(response.context['cart_total'], Decimal('120.00'))
        self.assertEqual(response.context['cart_quantity'], 3)


class CheckoutTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user('buyer', password='buyer12345')
        self.client_profile = Client.objects.create(
            user=self.user,
            first_name='Илья',
            last_name='Мартынов',
            birth_date=date(1994, 2, 14),
            phone='+375 (33) 201-21-31',
            email='buyer@example.com',
            address='Минск',
        )
        self.product_type = ProductType.objects.create(name='Фильтры')
        self.manufacturer = Manufacturer.objects.create(name='Parts Co', country='Germany')
        self.part = Part.objects.create(
            sku='O-1',
            name='Масляный фильтр',
            product_type=self.product_type,
            manufacturer=self.manufacturer,
            price=Decimal('100.00'),
            quantity=5,
            description='Товар для заказа',
        )
        self.promo = PromoCode.objects.create(
            code='ORDER10',
            description='Скидка на заказ.',
            discount_percent=10,
            starts_at=timezone.localdate() - timedelta(days=1),
            ends_at=timezone.localdate() + timedelta(days=30),
        )

    def payload(self, **extra):
        data = {
            'full_name': 'Мартынов Илья',
            'phone': '+375 (33) 201-21-31',
            'email': 'buyer@example.com',
            'delivery_method': 'pickup',
            'delivery_address': '',
            'payment_method': 'card',
            'promo_code': '',
            'comment': '',
            'card_number': '4111111111111111',
            'card_holder': 'ILYA MARTYNOV',
            'card_expiry': '2030-01',
            'card_cvc': '123',
            'agree': 'on',
        }
        data.update(extra)
        return data

    def test_checkout_redirects_when_cart_is_empty(self):
        self.client.login(username='buyer', password='buyer12345')
        self.assertRedirects(self.client.get(reverse('checkout')), reverse('part_list'))

    def test_checkout_requires_login(self):
        self.client.post(reverse('cart_add', args=[self.part.pk]), {'quantity': 1})
        response = self.client.get(reverse('checkout'))
        self.assertEqual(response.status_code, 302)
        self.assertIn(reverse('login'), response['Location'])

    def test_checkout_requires_client_profile(self):
        staff = User.objects.create_user('manager2', password='manager12345', is_staff=True)
        self.client.force_login(staff)
        self.client.post(reverse('cart_add', args=[self.part.pk]), {'quantity': 1})
        self.assertRedirects(
            self.client.get(reverse('checkout')),
            reverse('complete_client_profile'),
            target_status_code=302,
        )

    def test_checkout_page_available_with_items(self):
        self.client.login(username='buyer', password='buyer12345')
        self.client.post(reverse('cart_add', args=[self.part.pk]), {'quantity': 1})
        response = self.client.get(reverse('checkout'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Масляный фильтр')

    def test_successful_payment_creates_order_and_clears_cart(self):
        self.client.login(username='buyer', password='buyer12345')
        self.client.post(reverse('cart_add', args=[self.part.pk]), {'quantity': 2})
        response = self.client.post(reverse('checkout'), self.payload())
        order = Order.objects.get()
        self.assertRedirects(response, reverse('order_success', args=[order.pk]))
        self.assertEqual(order.status, Order.STATUS_PAID)
        self.assertEqual(order.total, Decimal('200.00'))
        self.assertEqual(OrderItem.objects.count(), 1)
        self.assertEqual(self.client.session['cart'], {})

    def test_payment_decreases_stock_exactly_once(self):
        self.client.login(username='buyer', password='buyer12345')
        self.client.post(reverse('cart_add', args=[self.part.pk]), {'quantity': 2})
        self.client.post(reverse('checkout'), self.payload())
        self.part.refresh_from_db()
        self.assertEqual(self.part.quantity, 3)
        self.assertEqual(Sale.objects.count(), 1)

    def test_payment_of_whole_stock_succeeds(self):
        self.client.login(username='buyer', password='buyer12345')
        self.client.post(reverse('cart_add', args=[self.part.pk]), {'quantity': 5})
        self.client.post(reverse('checkout'), self.payload())
        self.part.refresh_from_db()
        self.assertEqual(self.part.quantity, 0)
        self.assertEqual(Order.objects.count(), 1)

    def test_promo_code_reduces_order_total(self):
        self.client.login(username='buyer', password='buyer12345')
        self.client.post(reverse('cart_add', args=[self.part.pk]), {'quantity': 1})
        self.client.post(reverse('checkout'), self.payload(promo_code='ORDER10'))
        order = Order.objects.get()
        self.assertEqual(order.discount_percent, 10)
        self.assertEqual(order.total, Decimal('90.00'))

    def test_invalid_payment_shows_error_summary_at_top(self):
        self.client.login(username='buyer', password='buyer12345')
        self.client.post(reverse('cart_add', args=[self.part.pk]), {'quantity': 1})
        response = self.client.post(reverse('checkout'), self.payload(card_number=''))
        content = response.content.decode()
        self.assertEqual(Order.objects.count(), 0)
        self.assertContains(response, 'Заказ не оформлен')
        self.assertLess(content.index('Заказ не оформлен'), content.index('Состав заказа'))
        self.assertIn('Укажите номер карты', content)

    def test_checkout_with_stale_cart_does_not_create_empty_order(self):
        self.client.login(username='buyer', password='buyer12345')
        session = self.client.session
        session['cart'] = {'999999': 1}
        session.save()
        self.assertRedirects(self.client.get(reverse('checkout')), reverse('part_list'))
        self.client.post(reverse('checkout'), self.payload())
        self.assertEqual(Order.objects.count(), 0)

    def test_unknown_promo_code_is_rejected(self):
        self.client.login(username='buyer', password='buyer12345')
        self.client.post(reverse('cart_add', args=[self.part.pk]), {'quantity': 1})
        response = self.client.post(reverse('checkout'), self.payload(promo_code='NOPE'))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(Order.objects.count(), 0)
        self.assertContains(response, 'Промокод не найден')

    def test_guest_cannot_pay_and_no_order_is_created(self):
        self.client.post(reverse('cart_add', args=[self.part.pk]), {'quantity': 1})
        response = self.client.post(reverse('checkout'), self.payload())
        self.assertEqual(response.status_code, 302)
        self.assertEqual(Order.objects.count(), 0)
        self.part.refresh_from_db()
        self.assertEqual(self.part.quantity, 5)

    def test_cart_offers_login_to_guest(self):
        self.client.post(reverse('cart_add', args=[self.part.pk]), {'quantity': 1})
        response = self.client.get(reverse('cart_detail'))
        self.assertContains(response, 'Войти и оплатить заказ')
        self.client.login(username='buyer', password='buyer12345')
        response = self.client.get(reverse('cart_detail'))
        self.assertContains(response, 'Оплатить заказ')

    def test_paid_order_is_linked_to_user_and_client(self):
        self.client.login(username='buyer', password='buyer12345')
        self.client.post(reverse('cart_add', args=[self.part.pk]), {'quantity': 1})
        self.client.post(reverse('checkout'), self.payload())
        order = Order.objects.get()
        self.assertEqual(order.user, self.user)
        self.assertEqual(order.client, self.client_profile)

    def test_order_success_is_hidden_from_other_user(self):
        self.client.login(username='buyer', password='buyer12345')
        self.client.post(reverse('cart_add', args=[self.part.pk]), {'quantity': 1})
        self.client.post(reverse('checkout'), self.payload())
        order = Order.objects.get()
        stranger = User.objects.create_user('stranger', password='stranger12345')
        self.client.force_login(stranger)
        self.assertEqual(self.client.get(reverse('order_success', args=[order.pk])).status_code, 404)

    def test_paid_order_appears_in_profile(self):
        self.client.login(username='buyer', password='buyer12345')
        self.client.post(reverse('cart_add', args=[self.part.pk]), {'quantity': 1})
        self.client.post(reverse('checkout'), self.payload())
        response = self.client.get(reverse('profile'))
        self.assertContains(response, Order.objects.get().number)


class CheckoutFormTests(TestCase):
    def base_data(self, **extra):
        data = {
            'full_name': 'Мартынов Илья',
            'phone': '+375 (33) 201-21-31',
            'email': 'buyer@example.com',
            'delivery_method': 'pickup',
            'delivery_address': '',
            'payment_method': 'erip',
            'promo_code': '',
            'comment': '',
            'agree': 'on',
        }
        data.update(extra)
        return data

    def test_courier_delivery_requires_address(self):
        form = CheckoutForm(data=self.base_data(delivery_method='courier'))
        self.assertFalse(form.is_valid())
        self.assertIn('delivery_address', form.errors)

    def test_card_payment_requires_card_fields(self):
        form = CheckoutForm(data=self.base_data(payment_method='card'))
        self.assertFalse(form.is_valid())
        self.assertIn('card_number', form.errors)
        self.assertIn('card_cvc', form.errors)

    def test_card_number_must_contain_sixteen_digits(self):
        form = CheckoutForm(data=self.base_data(payment_method='card', card_number='4111', card_holder='IVAN IVANOV', card_expiry='2030-01', card_cvc='123'))
        self.assertFalse(form.is_valid())
        self.assertIn('card_number', form.errors)

    def test_delivery_date_cannot_be_in_the_past(self):
        past = (timezone.localdate() - timedelta(days=1)).isoformat()
        form = CheckoutForm(data=self.base_data(delivery_date=past))
        self.assertFalse(form.is_valid())
        self.assertIn('delivery_date', form.errors)

    def test_valid_form_without_card(self):
        self.assertTrue(CheckoutForm(data=self.base_data()).is_valid())


class FeedbackFormTests(TestCase):
    def base_data(self, **extra):
        data = {
            'name': 'Иван',
            'email': 'client@example.com',
            'phone': '+375 (29) 123-45-67',
            'topic': 'availability',
            'vin': '',
            'contact_method': 'phone',
            'message': 'Подберите, пожалуйста, масляный фильтр.',
            'agree': 'on',
        }
        data.update(extra)
        return data

    def test_vin_topic_requires_vin(self):
        form = FeedbackForm(data=self.base_data(topic='vin'))
        self.assertFalse(form.is_valid())
        self.assertIn('vin', form.errors)

    def test_short_vin_is_rejected(self):
        form = FeedbackForm(data=self.base_data(topic='vin', vin='WVWZZZ'))
        self.assertFalse(form.is_valid())
        self.assertIn('vin', form.errors)

    def test_wrong_phone_is_rejected(self):
        form = FeedbackForm(data=self.base_data(phone='80291234567'))
        self.assertFalse(form.is_valid())
        self.assertIn('phone', form.errors)

    def test_valid_feedback_is_accepted(self):
        form = FeedbackForm(data=self.base_data(topic='vin', vin='wvwzzz1kzaw000001', interests=['filters', 'oils']))
        self.assertTrue(form.is_valid())
        self.assertEqual(form.cleaned_data['vin'], 'WVWZZZ1KZAW000001')

    def test_feedback_view_saves_nothing_but_redirects(self):
        response = self.client.post(reverse('contacts'), self.base_data())
        self.assertEqual(response.status_code, 302)

    def test_invalid_feedback_view_renders_errors(self):
        response = self.client.post(reverse('contacts'), self.base_data(email='bad'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'errorlist')


class CompanyContentTests(TestCase):
    def setUp(self):
        CompanyProfile.objects.create(
            name='AutoParts',
            legal_name='ООО «АвтоПартс Групп»',
            slogan='Запчасти для планового обслуживания',
            description='Магазин автозапчастей.',
            founded_on=date(2016, 3, 14),
            unp='191234567',
            bank_account='BY86AKBB10100000002966000000',
            bank_name='ОАО «АСБ Беларусбанк»',
            bank_bic='AKBBBY2X',
            legal_address='Минск, ул. Монтажников, 12',
            phone='+375 (29) 100-10-10',
            email='info@autoparts.test',
            certificate_number='BY/112 03.11. 015 00123',
            certificate_authority='БелГИСС',
            certificate_issued_on=date(2024, 2, 19),
            certificate_valid_until=date(2027, 2, 18),
            certificate_text='Сертификат соответствия услуг розничной торговли.',
        )
        Partner.objects.create(
            name='Bosch',
            description='Датчики и электрика.',
            site_url='https://www.boschaftermarket.com/',
            logo_static_path='shop/img/partners/bosch.svg',
        )

    def test_about_page_shows_requisites_and_certificate(self):
        response = self.client.get(reverse('about'))
        self.assertContains(response, '191234567')
        self.assertContains(response, 'BY86AKBB10100000002966000000')
        self.assertContains(response, 'Сертификат соответствия')

    def test_home_page_shows_partner_with_external_link(self):
        response = self.client.get(reverse('home'))
        self.assertContains(response, 'Bosch')
        self.assertContains(response, 'https://www.boschaftermarket.com/')

    def test_home_slider_uses_delay_from_company_profile(self):
        response = self.client.get(reverse('home'))
        self.assertContains(response, 'data-delay="5"')
        self.assertNotContains(response, 'name="slider_delay"')

    def test_staff_can_change_slider_delay(self):
        User.objects.create_user('staff', password='staff12345', is_staff=True)
        self.client.login(username='staff', password='staff12345')
        self.assertContains(self.client.get(reverse('home')), 'name="slider_delay"')
        self.client.post(reverse('slider_settings'), {'slider_delay': '8'})
        self.assertEqual(CompanyProfile.objects.get().slider_delay, 8)
        self.client.post(reverse('slider_settings'), {'slider_delay': '0'})
        self.assertEqual(CompanyProfile.objects.get().slider_delay, 8)

    def test_regular_user_cannot_change_slider_delay(self):
        User.objects.create_user('user', password='user12345')
        self.client.login(username='user', password='user12345')
        self.client.post(reverse('slider_settings'), {'slider_delay': '8'})
        self.assertEqual(CompanyProfile.objects.get().slider_delay, 5)

    def test_privacy_page_is_filled(self):
        response = self.client.get(reverse('privacy'))
        self.assertContains(response, 'Политика конфиденциальности')
        self.assertContains(response, 'Сроки хранения')

# Create your tests here.

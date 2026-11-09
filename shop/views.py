import io
import logging
import os
import statistics
from collections import Counter
from decimal import Decimal

import requests
from django.contrib import messages
from django.contrib.auth import login
from django.contrib.auth.decorators import login_required, user_passes_test
from django.core.exceptions import ValidationError
from django.views.decorators.csrf import ensure_csrf_cookie
from django.db.models import Count, F, Q, Sum
from django.http import Http404, HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views.decorators.http import require_POST
from django.utils import timezone

from .cart import Cart
from .forms import (
    CheckoutForm,
    ClientProfileForm,
    FeedbackForm,
    PartForm,
    RegistrationForm,
    ReviewForm,
    SaleForm,
)
from .models import (
    Client,
    CompanyInfo,
    CompanyProfile,
    Employee,
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
    Term,
    Vacancy,
)
from .timeinfo import base_time_context as _base_time_context

logger = logging.getLogger(__name__)


def staff_required(view_func):
    return user_passes_test(lambda user: user.is_authenticated and (user.is_staff or user.is_superuser))(view_func)


def _safe_api_get(url, fallback, timeout=2):
    try:
        response = requests.get(url, timeout=timeout)
        response.raise_for_status()
        return response.json()
    except requests.RequestException as exc:
        logger.warning('External API failed: %s', exc)
        return fallback


def home(request):
    latest_news = NewsArticle.objects.filter(is_published=True).first()
    context = {
        'latest_news': latest_news,
        'catalog_types': ProductType.objects.all()[:6],
        'showcase_parts': Part.objects.select_related('product_type', 'manufacturer').filter(is_active=True)[:6],
        'partners': Partner.objects.filter(is_active=True),
        'parts_count': Part.objects.filter(is_active=True).count(),
        'suppliers_count': Supplier.objects.count(),
        'active_promos': PromoCode.objects.filter(is_active=True).count(),
    }
    context.update(_base_time_context())
    return render(request, 'shop/home.html', context)


@staff_required
@require_POST
def slider_settings(request):
    company = CompanyProfile.objects.first()
    try:
        delay = int(request.POST.get('slider_delay', ''))
    except ValueError:
        delay = 0
    if company and 1 <= delay <= 60:
        company.slider_delay = delay
        company.save(update_fields=['slider_delay', 'updated_at_utc', 'updated_at_local_text'])
        messages.success(request, f'Интервал смены слайдов: {delay} с.')
    else:
        messages.error(request, 'Интервал смены слайдов должен быть от 1 до 60 секунд.')
    return redirect('home')


def about(request):
    return render(
        request,
        'shop/about.html',
        {
            'items': CompanyInfo.objects.all(),
            'company': CompanyProfile.objects.first(),
            'partners': Partner.objects.filter(is_active=True),
            **_base_time_context(),
        },
    )


def news_list(request):
    return render(
        request,
        'shop/news_list.html',
        {'articles': NewsArticle.objects.filter(is_published=True), **_base_time_context()},
    )


def news_detail(request, slug):
    article = get_object_or_404(NewsArticle, slug=slug, is_published=True)
    return render(request, 'shop/news_detail.html', {'article': article, **_base_time_context()})


def terms(request):
    return render(request, 'shop/terms.html', {'terms': Term.objects.all(), **_base_time_context()})


def contacts(request):
    if request.method == 'POST':
        form = FeedbackForm(request.POST, request.FILES)
        if form.is_valid():
            logger.info('Feedback from %s on topic %s', form.cleaned_data['email'], form.cleaned_data['topic'])
            messages.success(request, 'Заявка отправлена, менеджер свяжется с вами в рабочее время.')
            return redirect(f"{reverse('contacts')}#feedback")
    else:
        initial = {}
        if request.user.is_authenticated:
            initial = {
                'name': request.user.first_name or request.user.username,
                'email': request.user.email,
            }
        form = FeedbackForm(initial=initial)
    return render(
        request,
        'shop/contacts.html',
        {
            'employees': Employee.objects.all(),
            'company': CompanyProfile.objects.first(),
            'form': form,
            **_base_time_context(),
        },
    )


def employees(request):
    return render(request, 'shop/employees.html', _base_time_context())


def employees_api(request):
    data = [
        {
            'id': employee.pk,
            'full_name': f'{employee.last_name} {employee.first_name}',
            'photo_url': employee.photo_url,
            'description': f'{employee.position}. {employee.responsibilities}',
            'phone': employee.phone,
            'email': employee.email,
        }
        for employee in Employee.objects.all()
    ]
    return JsonResponse({'results': data})


def js_tasks(request):
    return render(request, 'shop/js_tasks.html', _base_time_context())


def privacy(request):
    return render(request, 'shop/privacy.html', {'company': CompanyProfile.objects.first(), **_base_time_context()})


def vacancies(request):
    return render(request, 'shop/vacancies.html', {'vacancies': Vacancy.objects.all(), **_base_time_context()})


def reviews(request):
    return render(
        request,
        'shop/reviews.html',
        {'reviews': Review.objects.filter(is_approved=True), **_base_time_context()},
    )


@login_required
def review_create(request):
    if request.method == 'POST':
        form = ReviewForm(request.POST)
        if form.is_valid():
            review = form.save(commit=False)
            review.user = request.user
            review.name = request.user.get_full_name() or request.user.username
            review.save()
            messages.success(request, 'Отзыв сохранен.')
            return redirect('reviews')
    else:
        form = ReviewForm()
    return render(
        request,
        'shop/form.html',
        {
            'form': form,
            'title': 'Добавить отзыв',
            'submit_label': 'Отправить',
            'form_class': 'review-form',
            **_base_time_context(),
        },
    )


@login_required
def promos(request):
    return render(
        request,
        'shop/promos.html',
        {'promos': PromoCode.objects.prefetch_related('product_types'), **_base_time_context()},
    )


def part_list(request):
    parts = Part.objects.select_related('product_type', 'manufacturer').filter(is_active=True)
    types = ProductType.objects.all()
    selected_type = None
    type_id = request.GET.get('type')
    if type_id:
        selected_type = types.filter(pk=type_id).first()
        if selected_type:
            parts = parts.filter(product_type=selected_type)

    search_query = request.GET.get('q', '').strip()
    if search_query:
        search_filter = (
            Q(name__icontains=search_query)
            | Q(product_type__name__icontains=search_query)
            | Q(manufacturer__name__icontains=search_query)
        )
        if request.user.is_authenticated and (request.user.is_staff or request.user.is_superuser):
            search_filter |= Q(sku__icontains=search_query)
        parts = parts.filter(search_filter)

    sort = request.GET.get('sort', 'name')
    sort_map = {
        'name': 'name',
        'price': 'price',
        'price_desc': '-price',
        'quantity': 'quantity',
        'quantity_desc': '-quantity',
    }
    parts = parts.order_by(sort_map.get(sort, 'name'))

    return render(
        request,
        'shop/part_list.html',
        {
            'parts': parts,
            'types': types,
            'selected_type': selected_type,
            'current_sort': sort,
            'search_query': search_query,
            **_base_time_context(),
        },
    )


def part_detail(request, pk):
    part = get_object_or_404(
        Part.objects.select_related('product_type', 'manufacturer').prefetch_related('suppliers'),
        pk=pk,
    )
    similar_parts = (
        Part.objects.select_related('manufacturer')
        .filter(is_active=True, product_type=part.product_type)
        .exclude(pk=part.pk)[:3]
    )
    return render(
        request,
        'shop/part_detail.html',
        {
            'part': part,
            'similar_parts': similar_parts,
            'promos': PromoCode.objects.filter(is_active=True),
            **_base_time_context(),
        },
    )


@staff_required
def part_create(request):
    if request.method == 'POST':
        form = PartForm(request.POST)
        if form.is_valid():
            part = form.save()
            messages.success(request, 'Товар добавлен.')
            return redirect(part)
    else:
        form = PartForm()
    return render(request, 'shop/form.html', {'form': form, 'title': 'Новый товар', **_base_time_context()})


@staff_required
def part_update(request, pk):
    part = get_object_or_404(Part, pk=pk)
    if request.method == 'POST':
        form = PartForm(request.POST, instance=part)
        if form.is_valid():
            form.save()
            messages.success(request, 'Товар обновлен.')
            return redirect(part)
    else:
        form = PartForm(instance=part)
    return render(request, 'shop/form.html', {'form': form, 'title': 'Редактировать товар', **_base_time_context()})


@staff_required
def part_delete(request, pk):
    part = get_object_or_404(Part, pk=pk)
    if request.method == 'POST':
        part.is_active = False
        part.save(update_fields=['is_active', 'updated_at_utc', 'updated_at_local_text'])
        messages.success(request, 'Товар удален.')
        return redirect('part_list')
    return render(request, 'shop/confirm_delete.html', {'object': part, 'title': 'Удалить товар', **_base_time_context()})


def cart_detail(request):
    cart = Cart(request)
    return render(
        request,
        'shop/cart.html',
        {
            'cart': cart,
            'cart_total': cart.total(),
            'recommended_parts': Part.objects.filter(is_active=True, quantity__gt=0).order_by('price')[:3],
            **_base_time_context(),
        },
    )


@require_POST
def cart_add(request, pk):
    part = get_object_or_404(Part, pk=pk, is_active=True)
    if part.quantity < 1:
        messages.warning(request, f'Товара «{part.name}» нет на складе.')
        return redirect(part)
    try:
        quantity = int(request.POST.get('quantity', 1))
    except (TypeError, ValueError):
        quantity = 1
    cart = Cart(request)
    cart.add(part, quantity=quantity, replace=request.POST.get('replace') == 'true')
    messages.success(request, f'Товар «{part.name}» добавлен в корзину.')
    return redirect(request.POST.get('next') or 'cart_detail')


@require_POST
def cart_update(request, pk):
    part = get_object_or_404(Part, pk=pk)
    cart = Cart(request)
    action = request.POST.get('action')
    current = cart.cart.get(str(part.pk), 0)
    if action == 'increase':
        if current >= part.quantity:
            messages.warning(request, f'На складе осталось {part.quantity} шт. товара «{part.name}».')
        else:
            cart.add(part, quantity=current + 1, replace=True)
    elif action == 'decrease':
        if current <= 1:
            cart.remove(part)
            messages.info(request, f'Товар «{part.name}» удален из корзины.')
        else:
            cart.add(part, quantity=current - 1, replace=True)
    return redirect('cart_detail')


@require_POST
def cart_remove(request, pk):
    part = get_object_or_404(Part, pk=pk)
    Cart(request).remove(part)
    messages.info(request, f'Товар «{part.name}» удален из корзины.')
    return redirect('cart_detail')


@require_POST
def cart_clear(request):
    Cart(request).clear()
    messages.info(request, 'Корзина очищена.')
    return redirect('cart_detail')


@login_required
def checkout(request):
    cart = Cart(request)
    if cart.is_empty:
        messages.warning(request, 'Корзина пуста — добавьте товары перед оплатой.')
        return redirect('part_list')

    client = _get_client_profile(request.user)
    if not client:
        messages.warning(request, 'Для оформления заказа нужно заполнить профиль клиента.')
        return redirect('complete_client_profile')

    if request.method == 'POST':
        form = CheckoutForm(request.POST)
        if form.is_valid():
            rows = list(cart)
            if any(row['exceeds_stock'] for row in rows):
                messages.error(request, 'Количество в корзине превышает остаток на складе.')
                return redirect('cart_detail')
            discount = Decimal(form.promo.discount_percent) if form.promo else Decimal('0')
            order = form.save(commit=False)
            order.user = request.user
            order.client = client
            order.discount_percent = int(discount)
            order.status = Order.STATUS_NEW
            order.total = sum(
                ((row['total_price'] * (Decimal('100') - discount) / Decimal('100')).quantize(Decimal('0.01')) for row in rows),
                Decimal('0.00'),
            )
            order.save()
            for row in rows:
                unit_price = (row['unit_price'] * (Decimal('100') - discount) / Decimal('100')).quantize(Decimal('0.01'))
                OrderItem.objects.create(order=order, part=row['part'], quantity=row['quantity'], unit_price=unit_price)
            cart.clear()
            if order.payment_method == 'card':
                order.pay()
                messages.success(request, f'Заказ {order.number} оплачен.')
                return redirect('order_success', pk=order.pk)
            messages.info(request, f'Заказ {order.number} оформлен и ожидает оплаты.')
            return redirect('profile')
    else:
        form = CheckoutForm(
            initial={
                'full_name': f'{client.last_name} {client.first_name}',
                'phone': client.phone,
                'email': client.email,
                'delivery_address': client.address,
            }
        )

    return render(
        request,
        'shop/checkout.html',
        {
            'form': form,
            'cart': cart,
            'cart_total': cart.total(),
            'promos': PromoCode.objects.filter(is_active=True),
            'company': CompanyProfile.objects.first(),
            **_base_time_context(),
        },
    )


@login_required
def order_success(request, pk):
    order = get_object_or_404(Order.objects.prefetch_related('items__part'), pk=pk)
    if order.user_id != request.user.pk:
        raise Http404
    return render(
        request,
        'shop/order_success.html',
        {'order': order, 'company': CompanyProfile.objects.first(), **_base_time_context()},
    )


@login_required
@require_POST
def order_pay(request, pk):
    order = get_object_or_404(Order, pk=pk, user=request.user)
    try:
        order.pay()
    except ValidationError as exc:
        messages.error(request, exc.messages[0])
        return redirect('profile')
    messages.success(request, f'Заказ {order.number} оплачен.')
    return redirect('order_success', pk=order.pk)


@login_required
@require_POST
def order_cancel(request, pk):
    order = get_object_or_404(Order, pk=pk, user=request.user)
    try:
        order.cancel()
        messages.info(request, f'Заказ {order.number} отменен.')
    except ValidationError as exc:
        messages.error(request, exc.messages[0])
    return redirect('profile')


def _get_client_profile(user):
    try:
        return user.client_profile
    except Client.DoesNotExist:
        return None


@login_required
def sale_create(request):
    client = _get_client_profile(request.user)
    if not client:
        messages.warning(request, 'Для покупки нужно заполнить профиль клиента.')
        return redirect('complete_client_profile')
    if request.method == 'POST':
        form = SaleForm(request.POST, client=client)
        if form.is_valid():
            sale = form.save()
            message = f'Покупка сохранена: {sale.part.name}.'
            if form.promo:
                message += f' Промокод {form.promo.code}: скидка {form.promo.discount_percent}%.'
            messages.success(request, message)
            return redirect('profile')
    else:
        initial = {'part': request.GET.get('part')} if request.GET.get('part') else None
        form = SaleForm(client=client, initial=initial)
    return render(request, 'shop/form.html', {'form': form, 'title': 'Купить товар', **_base_time_context()})


@login_required
def complete_client_profile(request):
    if _get_client_profile(request.user):
        return redirect('profile')
    if request.user.is_staff or request.user.is_superuser:
        messages.info(request, 'Для сотрудников покупки оформляются через клиентский аккаунт.')
        return redirect('profile')
    if request.method == 'POST':
        form = ClientProfileForm(request.POST)
        if form.is_valid():
            client = form.save(commit=False)
            client.user = request.user
            client.save()
            request.user.first_name = client.first_name
            request.user.last_name = client.last_name
            request.user.email = client.email
            request.user.save(update_fields=['first_name', 'last_name', 'email'])
            messages.success(request, 'Профиль клиента сохранен. Теперь можно оформлять покупки.')
            return redirect('profile')
    else:
        form = ClientProfileForm(
            initial={
                'first_name': request.user.first_name,
                'last_name': request.user.last_name,
                'email': request.user.email,
            }
        )
    return render(
        request,
        'shop/form.html',
        {'form': form, 'title': 'Профиль клиента', **_base_time_context()},
    )


@login_required
def profile(request):
    client = _get_client_profile(request.user)
    employee = getattr(request.user, 'employee_profile', None)
    sales = Sale.objects.select_related('part').filter(client=client) if client else Sale.objects.none()
    staff_sales = Sale.objects.select_related('client', 'part').all()[:20] if request.user.is_staff else []
    orders = Order.objects.prefetch_related('items__part').filter(user=request.user)
    return render(
        request,
        'shop/profile.html',
        {
            'client': client,
            'employee': employee,
            'sales': sales,
            'staff_sales': staff_sales,
            'orders': orders,
            **_base_time_context(),
        },
    )


@ensure_csrf_cookie
def register(request):
    if request.method == 'POST':
        form = RegistrationForm(request.POST)
        if form.is_valid():
            user = form.save()
            login(request, user)
            if not _get_client_profile(user):
                messages.warning(request, 'Аккаунт создан. Заполните профиль клиента для покупок.')
                return redirect('complete_client_profile')
            messages.success(request, 'Регистрация завершена.')
            return redirect('profile')
    else:
        form = RegistrationForm()
    return render(request, 'shop/registration/register.html', {'form': form, **_base_time_context()})


def external_apis(request):
    cat_fact = _safe_api_get('https://catfact.ninja/fact', {'fact': 'API временно недоступен.'})
    ip_info = _safe_api_get('https://api.ipify.org?format=json', {'ip': 'не удалось получить'})
    return render(
        request,
        'shop/external_apis.html',
        {'cat_fact': cat_fact.get('fact'), 'ip': ip_info.get('ip'), **_base_time_context()},
    )


@login_required
def parts_api(request):
    fields = ['name', 'price', 'quantity']
    if request.user.is_staff or request.user.is_superuser:
        fields = ['sku', 'name', 'price', 'quantity']
    parts = Part.objects.filter(is_active=True).values(*fields)
    return JsonResponse({'results': list(parts)})


@staff_required
def stats(request):
    sales = Sale.objects.select_related('part', 'part__product_type')
    totals = [sale.total_price for sale in sales]
    type_counter = Counter()
    for sale in sales:
        type_counter[sale.part.product_type.name] += sale.quantity
    total_sum = sum(totals, Decimal('0.00'))
    stat_values = {
        'total_sum': total_sum,
        'average': statistics.mean(totals) if totals else Decimal('0.00'),
        'median': statistics.median(totals) if totals else Decimal('0.00'),
        'mode': statistics.mode(totals) if totals else Decimal('0.00'),
        'top_type': type_counter.most_common(1)[0][0] if type_counter else 'нет данных',
    }
    parts_by_name = Part.objects.order_by('name')
    return render(
        request,
        'shop/stats.html',
        {'stat_values': stat_values, 'parts_by_name': parts_by_name, **_base_time_context()},
    )


@staff_required
def sales_chart(request):
    os.environ.setdefault('MPLCONFIGDIR', os.path.join(os.getcwd(), '.matplotlib'))
    import matplotlib

    matplotlib.use('Agg')
    from matplotlib import pyplot as plt

    data = (
        Sale.objects.values(type_name=F('part__product_type__name'))
        .annotate(total=Sum(F('quantity') * F('unit_price')), count=Count('id'))
        .order_by('type_name')
    )
    labels = [row['type_name'] for row in data]
    values = [float(row['total'] or 0) for row in data]
    if not labels:
        labels = ['Нет продаж']
        values = [0]
    fig, ax = plt.subplots(figsize=(8, 4))
    ax.bar(labels, values, color='#2f6f73')
    ax.set_title('Выручка по типам товаров')
    ax.set_ylabel('BYN')
    ax.tick_params(axis='x', rotation=25)
    fig.tight_layout()
    buffer = io.BytesIO()
    fig.savefig(buffer, format='png')
    plt.close(fig)
    buffer.seek(0)
    return HttpResponse(buffer.getvalue(), content_type='image/png')

# Create your views here.

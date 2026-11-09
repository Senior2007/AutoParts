import re
from decimal import Decimal

from django.conf import settings
from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.core.validators import MaxValueValidator, MinValueValidator, RegexValidator
from django.db import models, transaction
from django.urls import reverse
from django.utils import timezone


phone_validator = RegexValidator(
    regex=r'^\+375 \((25|29|33|44)\) \d{3}-\d{2}-\d{2}$',
    message='Телефон должен быть в формате +375 (29) XXX-XX-XX.',
)

email_validator = RegexValidator(
    regex=r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$',
    message='Введите корректный email, например name@example.com.',
)


def validate_adult(value):
    today = timezone.localdate()
    age = today.year - value.year - ((today.month, today.day) < (value.month, value.day))
    if age < 18:
        raise ValidationError('Возраст клиента или сотрудника должен быть не меньше 18 лет.')


def validate_not_future(value):
    if value > timezone.localdate():
        raise ValidationError('Дата не может быть в будущем.')


class TimeStampedModel(models.Model):
    created_at_utc = models.DateTimeField(default=timezone.now, editable=False)
    updated_at_utc = models.DateTimeField(auto_now=True)
    created_at_timezone = models.CharField(max_length=64, default=settings.TIME_ZONE, editable=False)
    created_at_local_text = models.CharField(max_length=32, blank=True, editable=False)
    updated_at_local_text = models.CharField(max_length=32, blank=True, editable=False)

    class Meta:
        abstract = True

    def save(self, *args, **kwargs):
        now = timezone.now()
        if not self.created_at_local_text:
            self.created_at_local_text = timezone.localtime(self.created_at_utc).strftime('%d/%m/%Y %H:%M')
        self.created_at_timezone = settings.TIME_ZONE
        self.updated_at_local_text = timezone.localtime(now).strftime('%d/%m/%Y %H:%M')
        super().save(*args, **kwargs)


class CompanyInfo(TimeStampedModel):
    title = models.CharField(max_length=120)
    content = models.TextField()
    year = models.PositiveIntegerField(null=True, blank=True)
    logo_url = models.URLField(blank=True)

    class Meta:
        ordering = ['year', 'title']
        verbose_name = 'Информация о компании'
        verbose_name_plural = 'Информация о компании'

    def __str__(self):
        return self.title


class NewsArticle(TimeStampedModel):
    title = models.CharField(max_length=180)
    slug = models.SlugField(max_length=190, unique=True)
    summary = models.CharField(max_length=260)
    content = models.TextField()
    image_url = models.URLField(blank=True)
    published_at = models.DateTimeField(default=timezone.now)
    is_published = models.BooleanField(default=True)

    class Meta:
        ordering = ['-published_at']
        verbose_name = 'Новость'
        verbose_name_plural = 'Новости'

    def __str__(self):
        return self.title

    def get_absolute_url(self):
        return reverse('news_detail', args=[self.slug])


class Term(TimeStampedModel):
    title = models.CharField(max_length=120)
    definition = models.TextField()
    added_on = models.DateField(default=timezone.localdate, validators=[validate_not_future])

    class Meta:
        ordering = ['title']
        verbose_name = 'Термин'
        verbose_name_plural = 'Словарь терминов'

    def __str__(self):
        return self.title


class Vacancy(TimeStampedModel):
    title = models.CharField(max_length=120)
    description = models.TextField()
    salary_min = models.DecimalField(max_digits=10, decimal_places=2, validators=[MinValueValidator(0)])
    salary_max = models.DecimalField(max_digits=10, decimal_places=2, validators=[MinValueValidator(0)])
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ['-is_active', 'title']
        verbose_name = 'Вакансия'
        verbose_name_plural = 'Вакансии'

    def clean(self):
        if self.salary_max and self.salary_min and self.salary_max < self.salary_min:
            raise ValidationError('Максимальная зарплата не может быть меньше минимальной.')

    def __str__(self):
        return self.title


class ProductType(TimeStampedModel):
    name = models.CharField(max_length=100, unique=True)
    description = models.TextField(blank=True)

    class Meta:
        ordering = ['name']
        verbose_name = 'Тип товара'
        verbose_name_plural = 'Типы товаров'

    def __str__(self):
        return self.name


class Manufacturer(TimeStampedModel):
    name = models.CharField(max_length=120, unique=True)
    country = models.CharField(max_length=80)
    website = models.URLField(blank=True)

    class Meta:
        ordering = ['name']
        verbose_name = 'Изготовитель'
        verbose_name_plural = 'Изготовители'

    def __str__(self):
        return self.name


class Supplier(TimeStampedModel):
    name = models.CharField(max_length=140, unique=True)
    address = models.CharField(max_length=220)
    phone = models.CharField(max_length=20, validators=[phone_validator])
    email = models.EmailField()

    class Meta:
        ordering = ['name']
        verbose_name = 'Поставщик'
        verbose_name_plural = 'Поставщики'

    def __str__(self):
        return self.name


class Part(TimeStampedModel):
    sku = models.CharField(max_length=40, unique=True)
    name = models.CharField(max_length=160)
    product_type = models.ForeignKey(ProductType, on_delete=models.PROTECT, related_name='parts')
    manufacturer = models.ForeignKey(Manufacturer, on_delete=models.PROTECT, related_name='parts')
    suppliers = models.ManyToManyField(Supplier, through='Supply', related_name='parts')
    price = models.DecimalField(max_digits=10, decimal_places=2, validators=[MinValueValidator(Decimal('0.01'))])
    quantity = models.PositiveIntegerField(default=0)
    description = models.TextField()
    image_url = models.URLField(blank=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ['name']
        verbose_name = 'Товар'
        verbose_name_plural = 'Товары'

    def clean(self):
        if self.quantity < 0:
            raise ValidationError('Количество не может быть отрицательным.')

    def __str__(self):
        return f'{self.sku} - {self.name}'

    def get_absolute_url(self):
        return reverse('part_detail', args=[self.pk])

    @property
    def image_srcset(self):
        if not re.search(r'[?&]w=\d+', self.image_url):
            return ''
        return ', '.join(
            f"{re.sub(r'([?&])w=\d+', rf'\g<1>w={width}', self.image_url)} {width}w" for width in (480, 900, 1600)
        )


class Supply(TimeStampedModel):
    supplier = models.ForeignKey(Supplier, on_delete=models.CASCADE)
    part = models.ForeignKey(Part, on_delete=models.CASCADE)
    purchase_date = models.DateField(default=timezone.localdate, validators=[validate_not_future])
    quantity = models.PositiveIntegerField(validators=[MinValueValidator(1)])
    unit_price = models.DecimalField(max_digits=10, decimal_places=2, validators=[MinValueValidator(Decimal('0.01'))])

    class Meta:
        ordering = ['-purchase_date']
        verbose_name = 'Поставка'
        verbose_name_plural = 'Поставки'

    def __str__(self):
        return f'{self.supplier} -> {self.part}'


class Client(TimeStampedModel):
    user = models.OneToOneField(User, on_delete=models.CASCADE, null=True, blank=True, related_name='client_profile')
    first_name = models.CharField(max_length=80)
    last_name = models.CharField(max_length=80)
    birth_date = models.DateField(validators=[validate_adult, validate_not_future])
    phone = models.CharField(max_length=20, validators=[phone_validator])
    email = models.EmailField()
    address = models.CharField(max_length=220)

    class Meta:
        ordering = ['last_name', 'first_name']
        verbose_name = 'Клиент'
        verbose_name_plural = 'Клиенты'

    def __str__(self):
        return f'{self.last_name} {self.first_name}'


class Employee(TimeStampedModel):
    user = models.OneToOneField(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='employee_profile')
    first_name = models.CharField(max_length=80)
    last_name = models.CharField(max_length=80)
    position = models.CharField(max_length=120)
    birth_date = models.DateField(validators=[validate_adult, validate_not_future])
    phone = models.CharField(max_length=20, validators=[phone_validator])
    email = models.EmailField()
    photo_url = models.URLField(blank=True)
    responsibilities = models.TextField()

    class Meta:
        ordering = ['last_name', 'first_name']
        verbose_name = 'Сотрудник'
        verbose_name_plural = 'Сотрудники'

    def __str__(self):
        return f'{self.last_name} {self.first_name}'


class Sale(TimeStampedModel):
    client = models.ForeignKey(Client, on_delete=models.PROTECT, related_name='sales')
    part = models.ForeignKey(Part, on_delete=models.PROTECT, related_name='sales')
    employee = models.ForeignKey(Employee, on_delete=models.SET_NULL, null=True, blank=True, related_name='sales')
    sold_at = models.DateTimeField(default=timezone.now)
    quantity = models.PositiveIntegerField(validators=[MinValueValidator(1)])
    unit_price = models.DecimalField(max_digits=10, decimal_places=2, validators=[MinValueValidator(Decimal('0.01'))])

    class Meta:
        ordering = ['-sold_at']
        verbose_name = 'Продажа'
        verbose_name_plural = 'Продажи'

    @property
    def total_price(self):
        return self.quantity * self.unit_price

    def clean(self):
        if self.part_id and self.quantity and self.quantity > self.part.quantity:
            raise ValidationError('На складе недостаточно товара для продажи.')

    def save(self, *args, **kwargs):
        is_new = self.pk is None
        self.full_clean()
        if is_new:
            self.part.quantity -= self.quantity
            self.part.save(update_fields=['quantity', 'updated_at_utc', 'updated_at_local_text'])
        super().save(*args, **kwargs)

    def __str__(self):
        return f'{self.part} x {self.quantity}'


class Review(TimeStampedModel):
    user = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
    name = models.CharField(max_length=120)
    rating = models.PositiveSmallIntegerField(validators=[MinValueValidator(1), MaxValueValidator(5)])
    text = models.TextField()
    is_approved = models.BooleanField(default=True)

    class Meta:
        ordering = ['-created_at_utc']
        verbose_name = 'Отзыв'
        verbose_name_plural = 'Отзывы'

    def __str__(self):
        return f'{self.name}: {self.rating}'


class PromoCode(TimeStampedModel):
    code = models.CharField(max_length=40, unique=True)
    description = models.TextField()
    discount_percent = models.PositiveSmallIntegerField(validators=[MinValueValidator(1), MaxValueValidator(90)])
    starts_at = models.DateField()
    ends_at = models.DateField()
    is_active = models.BooleanField(default=True)
    product_types = models.ManyToManyField(
        ProductType,
        blank=True,
        related_name='promo_codes',
        verbose_name='Типы товаров',
        help_text='Пусто — промокод действует на любой товар.',
    )

    class Meta:
        ordering = ['-is_active', 'ends_at']
        verbose_name = 'Промокод'
        verbose_name_plural = 'Промокоды'

    def clean(self):
        if self.ends_at < self.starts_at:
            raise ValidationError('Дата окончания не может быть раньше даты начала.')

    def applies_to_part(self, part):
        if not self.product_types.exists():
            return True
        return self.product_types.filter(pk=part.product_type_id).exists()

    @property
    def is_current(self):
        today = timezone.localdate()
        return self.is_active and self.starts_at <= today <= self.ends_at

    def __str__(self):
        return self.code


class Partner(TimeStampedModel):
    name = models.CharField(max_length=120, unique=True)
    description = models.CharField(max_length=240)
    site_url = models.URLField()
    logo_static_path = models.CharField(max_length=200)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ['-is_active', 'name']
        verbose_name = 'Партнер'
        verbose_name_plural = 'Компании-партнеры'

    def __str__(self):
        return self.name


class CompanyProfile(TimeStampedModel):
    name = models.CharField(max_length=120)
    legal_name = models.CharField(max_length=200)
    slogan = models.CharField(max_length=200)
    description = models.TextField()
    founded_on = models.DateField()
    logo_static_path = models.CharField(max_length=200, blank=True)
    video_mp4_url = models.URLField(blank=True)
    video_webm_url = models.URLField(blank=True)
    video_embed_url = models.URLField(blank=True)
    video_poster_url = models.URLField(blank=True)
    unp = models.CharField(max_length=16)
    bank_account = models.CharField(max_length=40)
    bank_name = models.CharField(max_length=160)
    bank_bic = models.CharField(max_length=16)
    legal_address = models.CharField(max_length=220)
    phone = models.CharField(max_length=20, validators=[phone_validator])
    email = models.EmailField()
    certificate_number = models.CharField(max_length=40)
    certificate_authority = models.CharField(max_length=200)
    certificate_issued_on = models.DateField()
    certificate_valid_until = models.DateField()
    certificate_text = models.TextField()
    slider_delay = models.PositiveSmallIntegerField(
        'Интервал смены слайдов, с',
        default=5,
        validators=[MinValueValidator(1), MaxValueValidator(60)],
    )

    class Meta:
        verbose_name = 'Профиль компании'
        verbose_name_plural = 'Профиль компании'

    def __str__(self):
        return self.name


class Order(TimeStampedModel):
    STATUS_NEW = 'new'
    STATUS_PAID = 'paid'
    STATUS_CANCELED = 'canceled'
    STATUS_CHOICES = [
        (STATUS_NEW, 'Ожидает оплаты'),
        (STATUS_PAID, 'Оплачен'),
        (STATUS_CANCELED, 'Отменен'),
    ]

    DELIVERY_CHOICES = [
        ('pickup', 'Самовывоз со склада'),
        ('courier', 'Курьер по Минску'),
        ('post', 'Отправка по Беларуси'),
    ]

    PAYMENT_CHOICES = [
        ('card', 'Банковская карта'),
        ('erip', 'ЕРИП'),
        ('invoice', 'Счет для юридического лица'),
    ]

    user = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='orders')
    client = models.ForeignKey(Client, on_delete=models.SET_NULL, null=True, blank=True, related_name='orders')
    full_name = models.CharField(max_length=160)
    phone = models.CharField(max_length=20, validators=[phone_validator])
    email = models.EmailField(validators=[email_validator])
    delivery_method = models.CharField(max_length=16, choices=DELIVERY_CHOICES, default='pickup')
    payment_method = models.CharField(max_length=16, choices=PAYMENT_CHOICES, default='card')
    delivery_address = models.CharField(max_length=220, blank=True)
    delivery_date = models.DateField(null=True, blank=True)
    comment = models.TextField(blank=True)
    promo_code = models.CharField(max_length=40, blank=True)
    discount_percent = models.PositiveSmallIntegerField(default=0)
    total = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('0.00'))
    status = models.CharField(max_length=16, choices=STATUS_CHOICES, default=STATUS_NEW)
    paid_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ['-created_at_utc']
        verbose_name = 'Заказ'
        verbose_name_plural = 'Заказы'

    def __str__(self):
        return f'Заказ №{self.pk}'

    @property
    def number(self):
        return f'AP-{self.pk:06d}'

    @property
    def positions_count(self):
        return sum(item.quantity for item in self.items.all())

    def get_absolute_url(self):
        return reverse('order_success', args=[self.pk])

    def pay(self):
        """Переход new -> paid: списывает товар со склада и записывает продажи."""
        if self.status != self.STATUS_NEW:
            raise ValidationError('Оплатить можно только заказ, ожидающий оплаты.')
        with transaction.atomic():
            items = list(self.items.select_related('part'))
            if not items:
                raise ValidationError('В заказе нет позиций.')
            for item in items:
                if item.quantity > item.part.quantity:
                    raise ValidationError(f'На складе недостаточно товара «{item.part.name}».')
            for item in items:
                Sale.objects.create(client=self.client, part=item.part, quantity=item.quantity, unit_price=item.unit_price)
            self.status = self.STATUS_PAID
            self.paid_at = timezone.now()
            self.save(update_fields=['status', 'paid_at', 'updated_at_utc', 'updated_at_local_text'])

    def cancel(self):
        """Переход new -> canceled. Оплаченный заказ отменить нельзя."""
        if self.status != self.STATUS_NEW:
            raise ValidationError('Отменить можно только заказ, ожидающий оплаты.')
        self.status = self.STATUS_CANCELED
        self.save(update_fields=['status', 'updated_at_utc', 'updated_at_local_text'])


class OrderItem(TimeStampedModel):
    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name='items')
    part = models.ForeignKey(Part, on_delete=models.PROTECT, related_name='order_items')
    quantity = models.PositiveIntegerField(validators=[MinValueValidator(1)])
    unit_price = models.DecimalField(max_digits=10, decimal_places=2, validators=[MinValueValidator(Decimal('0.01'))])

    class Meta:
        ordering = ['pk']
        verbose_name = 'Позиция заказа'
        verbose_name_plural = 'Позиции заказа'

    @property
    def total_price(self):
        return self.quantity * self.unit_price

    def __str__(self):
        return f'{self.part} x {self.quantity}'

# Create your models here.

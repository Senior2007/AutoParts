from datetime import timedelta
from decimal import Decimal

from django import forms
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone

from .models import (
    Client,
    Order,
    Part,
    PromoCode,
    Review,
    Sale,
    email_validator,
    phone_validator,
    validate_adult,
)


EMAIL_HTML_PATTERN = r'[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}'

class RegistrationForm(UserCreationForm):
    first_name = forms.CharField(max_length=80, label='Имя')
    last_name = forms.CharField(max_length=80, label='Фамилия')
    birth_date = forms.DateField(
        label='Дата рождения',
        widget=forms.DateInput(attrs={'type': 'date'}),
    )
    phone = forms.CharField(max_length=20, label='Телефон', help_text='+375 (29) XXX-XX-XX', validators=[phone_validator])
    email = forms.EmailField(label='Email', validators=[email_validator])
    address = forms.CharField(max_length=220, label='Адрес')

    class Meta(UserCreationForm.Meta):
        model = User
        fields = ('username', 'first_name', 'last_name', 'email')

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        today = timezone.localdate()
        max_birth_date = today.replace(year=today.year - 18)
        self.fields['birth_date'].widget.attrs['max'] = max_birth_date.isoformat()
        self.fields['phone'].widget.attrs.update(
            {
                'pattern': phone_validator.regex.pattern,
                'title': '+375 (29) XXX-XX-XX',
            }
        )
        self.fields['email'].widget.attrs.update(
            {
                'pattern': EMAIL_HTML_PATTERN,
                'title': 'Например name@example.com',
            }
        )
        self.fields['password1'].help_text = ''
        self.fields['username'].help_text = 'Не более 150 символов: буквы, цифры и символы @/./+/-/_'

    def clean_email(self):
        email = self.cleaned_data['email'].strip()
        if User.objects.filter(email__iexact=email).exists():
            raise ValidationError('Пользователь с таким email уже зарегистрирован.')
        if Client.objects.filter(email__iexact=email).exists():
            raise ValidationError('Клиент с таким email уже существует.')
        return email

    def clean_birth_date(self):
        birth_date = self.cleaned_data['birth_date']
        validate_adult(birth_date)
        return birth_date

    def save(self, commit=True):
        with transaction.atomic():
            user = super().save(commit=False)
            user.first_name = self.cleaned_data['first_name']
            user.last_name = self.cleaned_data['last_name']
            user.email = self.cleaned_data['email']
            if commit:
                user.save()
                Client.objects.create(
                    user=user,
                    first_name=self.cleaned_data['first_name'],
                    last_name=self.cleaned_data['last_name'],
                    birth_date=self.cleaned_data['birth_date'],
                    phone=self.cleaned_data['phone'],
                    email=self.cleaned_data['email'],
                    address=self.cleaned_data['address'],
                )
        return user


class ClientProfileForm(forms.ModelForm):
    class Meta:
        model = Client
        fields = ('first_name', 'last_name', 'birth_date', 'phone', 'email', 'address')
        widgets = {
            'birth_date': forms.DateInput(attrs={'type': 'date'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        today = timezone.localdate()
        max_birth_date = today.replace(year=today.year - 18)
        self.fields['birth_date'].widget.attrs['max'] = max_birth_date.isoformat()
        self.fields['phone'].widget.attrs.update(
            {
                'pattern': phone_validator.regex.pattern,
                'title': '+375 (29) XXX-XX-XX',
            }
        )
        self.fields['email'].widget.attrs.update(
            {
                'pattern': EMAIL_HTML_PATTERN,
                'title': 'Например name@example.com',
            }
        )

    def clean_birth_date(self):
        birth_date = self.cleaned_data['birth_date']
        validate_adult(birth_date)
        return birth_date


class PartForm(forms.ModelForm):
    class Meta:
        model = Part
        fields = (
            'sku',
            'name',
            'product_type',
            'manufacturer',
            'price',
            'quantity',
            'description',
            'image_url',
            'is_active',
        )
        widgets = {
            'description': forms.Textarea(attrs={'rows': 5}),
        }


class ReviewForm(forms.ModelForm):
    RATING_CHOICES = [
        (5, '5 — отлично'),
        (4, '4 — хорошо'),
        (3, '3 — нормально'),
        (2, '2 — плохо'),
        (1, '1 — очень плохо'),
    ]

    class Meta:
        model = Review
        fields = ('rating', 'text')
        labels = {'rating': 'Оценка', 'text': 'Текст отзыва'}
        widgets = {
            'text': forms.Textarea(attrs={'cols': 60, 'rows': 4, 'minlength': 10, 'maxlength': 1000}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['rating'].widget = forms.Select(choices=self.RATING_CHOICES)
        self.fields['rating'].initial = 5


class SaleForm(forms.ModelForm):
    promo_code = forms.CharField(
        label='Промокод',
        required=False,
        max_length=40,
        help_text='Необязательно. Действующие коды — на странице «Промокоды».',
    )

    class Meta:
        model = Sale
        fields = ('part', 'quantity')
        widgets = {
            'quantity': forms.NumberInput(attrs={'min': 1}),
        }

    def __init__(self, *args, **kwargs):
        self.client = kwargs.pop('client')
        super().__init__(*args, **kwargs)
        self.fields['part'].queryset = Part.objects.filter(is_active=True, quantity__gt=0)
        self.promo = None

    def clean_promo_code(self):
        code = self.cleaned_data.get('promo_code', '').strip()
        if not code:
            return ''
        try:
            promo = PromoCode.objects.get(code__iexact=code)
        except PromoCode.DoesNotExist:
            raise ValidationError('Промокод не найден.')
        if not promo.is_current:
            raise ValidationError('Промокод недействителен или просрочен.')
        self.promo = promo
        return promo.code

    def clean(self):
        cleaned_data = super().clean()
        part = cleaned_data.get('part')
        quantity = cleaned_data.get('quantity')
        if part and quantity and quantity > part.quantity:
            raise ValidationError('На складе нет такого количества товара.')
        if self.promo and part and not self.promo.applies_to_part(part):
            type_names = ', '.join(self.promo.product_types.values_list('name', flat=True))
            raise ValidationError(
                f'Промокод {self.promo.code} не действует для типа «{part.product_type.name}». '
                f'Доступные типы: {type_names}.'
            )
        return cleaned_data

    def save(self, commit=True):
        sale = super().save(commit=False)
        sale.client = self.client
        unit_price = sale.part.price
        if self.promo:
            discount = Decimal(self.promo.discount_percent)
            unit_price = (unit_price * (Decimal('100') - discount) / Decimal('100')).quantize(Decimal('0.01'))
        sale.unit_price = unit_price
        if commit:
            sale.save()
        return sale


class CheckoutForm(forms.ModelForm):
    card_number = forms.CharField(
        label='Номер карты',
        max_length=19,
        required=False,
        help_text='16 цифр, можно с пробелами.',
    )
    card_holder = forms.CharField(label='Держатель карты', max_length=60, required=False)
    card_expiry = forms.CharField(label='Действует до', max_length=7, required=False)
    card_cvc = forms.CharField(label='CVC/CVV', max_length=3, required=False)
    agree = forms.BooleanField(label='Согласен с условиями оферты и политикой конфиденциальности')
    subscribe = forms.BooleanField(label='Присылать новости и промокоды', required=False)

    class Meta:
        model = Order
        fields = (
            'full_name',
            'phone',
            'email',
            'delivery_method',
            'delivery_address',
            'delivery_date',
            'payment_method',
            'promo_code',
            'comment',
        )
        labels = {
            'full_name': 'Фамилия и имя',
            'phone': 'Телефон',
            'email': 'Электронная почта',
            'delivery_method': 'Способ получения',
            'delivery_address': 'Адрес доставки',
            'delivery_date': 'Желаемая дата получения',
            'payment_method': 'Способ оплаты',
            'promo_code': 'Промокод',
            'comment': 'Комментарий к заказу',
        }
        widgets = {
            'delivery_method': forms.RadioSelect,
            'delivery_date': forms.DateInput(attrs={'type': 'date'}),
            'comment': forms.Textarea(attrs={'cols': 60, 'rows': 4, 'maxlength': 400}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.promo = None
        today = timezone.localdate()
        self.fields['full_name'].widget.attrs.update(
            {
                'minlength': 5,
                'autocomplete': 'name',
                'placeholder': 'Иванов Иван',
                'pattern': r'[А-Яа-яЁёA-Za-z\- ]{5,160}',
                'title': 'Фамилия и имя кириллицей или латиницей, минимум 5 символов',
            }
        )
        self.fields['phone'].widget.input_type = 'tel'
        self.fields['phone'].widget.attrs.update(
            {
                'inputmode': 'tel',
                'autocomplete': 'tel',
                'placeholder': '+375 (29) 123-45-67',
                'pattern': phone_validator.regex.pattern,
                'title': '+375 (29) XXX-XX-XX',
            }
        )
        self.fields['email'].widget.attrs.update(
            {
                'autocomplete': 'email',
                'placeholder': 'client@example.com',
                'pattern': EMAIL_HTML_PATTERN,
                'title': 'Например name@example.com',
            }
        )
        self.fields['delivery_address'].widget.attrs.update(
            {'placeholder': 'Минск, ул. Немига, 6', 'autocomplete': 'address-line1', 'maxlength': 220}
        )
        self.fields['delivery_date'].widget.attrs.update(
            {'min': today.isoformat(), 'max': (today + timedelta(days=30)).isoformat()}
        )
        self.fields['promo_code'].widget.attrs.update(
            {'list': 'promo-codes', 'placeholder': 'FILTER10', 'maxlength': 40, 'autocapitalize': 'characters'}
        )
        self.fields['comment'].widget.attrs.update({'placeholder': 'Уточните марку и модель автомобиля'})
        self.fields['card_number'].widget.attrs.update(
            {
                'inputmode': 'numeric',
                'autocomplete': 'off',
                'placeholder': '4111 1111 1111 1111',
                'pattern': r'[0-9 ]{16,19}',
                'title': '16 цифр номера карты',
            }
        )
        self.fields['card_holder'].widget.attrs.update(
            {'placeholder': 'IVAN IVANOV', 'pattern': '[A-Za-z ]{5,60}', 'title': 'Имя латинскими буквами, как на карте'}
        )
        self.fields['card_expiry'].widget = forms.DateInput(attrs={'type': 'month', 'min': today.strftime('%Y-%m')})
        self.fields['card_cvc'].widget = forms.PasswordInput(
            attrs={'inputmode': 'numeric', 'pattern': r'\d{3}', 'maxlength': 3, 'title': 'Три цифры с обратной стороны карты'}
        )

    def clean_promo_code(self):
        code = self.cleaned_data.get('promo_code', '').strip()
        if not code:
            return ''
        try:
            promo = PromoCode.objects.get(code__iexact=code)
        except PromoCode.DoesNotExist:
            raise ValidationError('Промокод не найден.')
        if not promo.is_current:
            raise ValidationError('Промокод недействителен или просрочен.')
        self.promo = promo
        return promo.code

    def clean_delivery_date(self):
        delivery_date = self.cleaned_data.get('delivery_date')
        if delivery_date and delivery_date < timezone.localdate():
            raise ValidationError('Дата получения не может быть в прошлом.')
        return delivery_date

    def clean_card_number(self):
        digits = self.cleaned_data.get('card_number', '').replace(' ', '')
        if digits and (not digits.isdigit() or len(digits) != 16):
            raise ValidationError('Номер карты состоит из 16 цифр.')
        return digits

    def clean(self):
        cleaned_data = super().clean()
        delivery_method = cleaned_data.get('delivery_method')
        address = cleaned_data.get('delivery_address', '').strip()
        if delivery_method in {'courier', 'post'} and not address:
            self.add_error('delivery_address', 'Для доставки нужно указать адрес.')
        if cleaned_data.get('payment_method') == 'card':
            for field, message in [
                ('card_number', 'Укажите номер карты.'),
                ('card_holder', 'Укажите держателя карты.'),
                ('card_expiry', 'Укажите срок действия карты.'),
                ('card_cvc', 'Укажите код CVC/CVV.'),
            ]:
                if not cleaned_data.get(field):
                    self.add_error(field, message)
        cvc = cleaned_data.get('card_cvc', '')
        if cvc and (not cvc.isdigit() or len(cvc) != 3):
            self.add_error('card_cvc', 'Код CVC/CVV состоит из трех цифр.')
        return cleaned_data


class FeedbackForm(forms.Form):
    TOPIC_CHOICES = [
        (
            'Каталог и подбор',
            [
                ('vin', 'Подбор детали по VIN'),
                ('availability', 'Наличие позиции на складе'),
                ('analog', 'Подбор аналога'),
            ],
        ),
        (
            'Заказ и доставка',
            [
                ('order', 'Статус заказа'),
                ('delivery', 'Условия доставки'),
                ('warranty', 'Гарантия и возврат'),
            ],
        ),
        (
            'Сотрудничество',
            [
                ('b2b', 'Работа с СТО'),
                ('vacancy', 'Вопрос по вакансии'),
            ],
        ),
    ]

    CONTACT_CHOICES = [
        ('phone', 'Телефонный звонок'),
        ('email', 'Письмо на почту'),
        ('messenger', 'Сообщение в мессенджер'),
    ]

    name = forms.CharField(
        label='Как к вам обращаться',
        min_length=2,
        max_length=80,
        widget=forms.TextInput(
            attrs={
                'placeholder': 'Иван',
                'autocomplete': 'given-name',
                'pattern': r'[А-Яа-яЁёA-Za-z\- ]{2,80}',
                'title': 'Только буквы, минимум 2 символа',
                'minlength': 2,
            }
        ),
    )
    email = forms.EmailField(
        label='Электронная почта',
        validators=[email_validator],
        widget=forms.EmailInput(
            attrs={'placeholder': 'client@example.com', 'autocomplete': 'email', 'pattern': EMAIL_HTML_PATTERN}
        ),
    )
    phone = forms.CharField(
        label='Телефон',
        validators=[phone_validator],
        widget=forms.TextInput(
            attrs={
                'inputmode': 'tel',
                'autocomplete': 'tel',
                'placeholder': '+375 (29) 123-45-67',
                'pattern': phone_validator.regex.pattern,
                'title': '+375 (29) XXX-XX-XX',
            }
        ),
    )
    topic = forms.ChoiceField(label='Тема обращения', choices=TOPIC_CHOICES)
    vin = forms.CharField(
        label='VIN автомобиля',
        required=False,
        max_length=17,
        widget=forms.TextInput(
            attrs={
                'placeholder': 'WVWZZZ1KZAW000001',
                'pattern': '[A-HJ-NPR-Za-hj-npr-z0-9]{17}',
                'title': '17 символов VIN без букв I, O, Q',
                'maxlength': 17,
                'spellcheck': 'false',
            }
        ),
    )
    interests = forms.MultipleChoiceField(
        label='Интересующие разделы каталога',
        required=False,
        choices=[
            ('filters', 'Фильтры'),
            ('brakes', 'Тормозная система'),
            ('suspension', 'Подвеска'),
            ('electric', 'Электрика'),
            ('oils', 'Масла и жидкости'),
            ('optics', 'Оптика'),
        ],
        widget=forms.SelectMultiple(attrs={'size': 6}),
        help_text='Несколько значений выбираются с зажатой клавишей Ctrl или Cmd.',
    )
    production_year = forms.IntegerField(
        label='Год выпуска автомобиля',
        required=False,
        min_value=1980,
        max_value=2026,
        widget=forms.NumberInput(attrs={'min': 1980, 'max': 2026, 'step': 1, 'placeholder': '2014'}),
    )
    budget = forms.IntegerField(
        label='Ориентировочный бюджет, BYN',
        initial=300,
        required=False,
        min_value=50,
        max_value=3000,
        widget=forms.NumberInput(
            attrs={'type': 'range', 'min': 50, 'max': 3000, 'step': 50, 'oninput': 'budgetOutput.value = this.value'}
        ),
    )
    call_date = forms.DateField(
        label='Удобная дата звонка',
        required=False,
        widget=forms.DateInput(attrs={'type': 'date'}),
    )
    call_time = forms.TimeField(
        label='Удобное время звонка',
        required=False,
        widget=forms.TimeInput(attrs={'type': 'time', 'min': '09:00', 'max': '19:00', 'step': 900}),
    )
    contact_method = forms.ChoiceField(
        label='Как удобнее ответить',
        choices=CONTACT_CHOICES,
        initial='phone',
        widget=forms.RadioSelect,
    )
    reference_url = forms.URLField(
        label='Ссылка на объявление или карточку детали',
        required=False,
        assume_scheme='https',
        widget=forms.URLInput(attrs={'placeholder': 'https://example.com/part/12345'}),
    )
    attachment = forms.FileField(
        label='Фото детали или скан документа',
        required=False,
        widget=forms.ClearableFileInput(attrs={'accept': '.jpg,.jpeg,.png,.pdf'}),
    )
    message = forms.CharField(
        label='Сообщение',
        min_length=10,
        max_length=600,
        widget=forms.Textarea(
            attrs={'cols': 60, 'rows': 5, 'minlength': 10, 'maxlength': 600, 'placeholder': 'Опишите деталь и автомобиль'}
        ),
    )
    agree = forms.BooleanField(label='Согласен на обработку персональных данных')

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['phone'].widget.input_type = 'tel'

    def clean_vin(self):
        vin = self.cleaned_data.get('vin', '').strip().upper()
        if vin and len(vin) != 17:
            raise ValidationError('VIN состоит из 17 символов.')
        return vin

    def clean(self):
        cleaned_data = super().clean()
        if cleaned_data.get('topic') == 'vin' and not cleaned_data.get('vin'):
            self.add_error('vin', 'Для подбора по VIN укажите номер кузова.')
        return cleaned_data

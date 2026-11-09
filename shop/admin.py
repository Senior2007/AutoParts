from django.contrib import admin

from .models import (
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
)


class SupplyInline(admin.TabularInline):
    model = Supply
    extra = 1


@admin.register(Part)
class PartAdmin(admin.ModelAdmin):
    list_display = ('sku', 'name', 'product_type', 'manufacturer', 'price', 'quantity', 'is_active')
    list_filter = ('product_type', 'manufacturer', 'is_active')
    search_fields = ('sku', 'name', 'description')
    inlines = [SupplyInline]


@admin.register(Supplier)
class SupplierAdmin(admin.ModelAdmin):
    list_display = ('name', 'phone', 'email', 'address')
    search_fields = ('name', 'phone', 'email')
    inlines = [SupplyInline]


@admin.register(Sale)
class SaleAdmin(admin.ModelAdmin):
    list_display = ('part', 'client', 'quantity', 'unit_price', 'sold_at')
    list_filter = ('sold_at', 'part__product_type')
    search_fields = ('part__name', 'client__last_name', 'client__phone')
    autocomplete_fields = ('part', 'client', 'employee')


@admin.register(Client)
class ClientAdmin(admin.ModelAdmin):
    list_display = ('last_name', 'first_name', 'phone', 'email', 'birth_date')
    search_fields = ('last_name', 'first_name', 'phone', 'email')


@admin.register(Employee)
class EmployeeAdmin(admin.ModelAdmin):
    list_display = ('last_name', 'first_name', 'position', 'phone', 'email')
    list_filter = ('position',)
    search_fields = ('last_name', 'first_name', 'phone', 'email')


@admin.register(NewsArticle)
class NewsArticleAdmin(admin.ModelAdmin):
    list_display = ('title', 'published_at', 'is_published')
    list_filter = ('is_published', 'published_at')
    search_fields = ('title', 'summary', 'content')
    prepopulated_fields = {'slug': ('title',)}


@admin.register(Review)
class ReviewAdmin(admin.ModelAdmin):
    list_display = ('name', 'rating', 'is_approved', 'created_at_utc')
    list_filter = ('rating', 'is_approved')
    search_fields = ('name', 'text')


@admin.register(PromoCode)
class PromoCodeAdmin(admin.ModelAdmin):
    list_display = ('code', 'discount_percent', 'starts_at', 'ends_at', 'is_active')
    list_filter = ('is_active', 'starts_at', 'ends_at', 'product_types')
    search_fields = ('code', 'description')
    filter_horizontal = ('product_types',)


class OrderItemInline(admin.TabularInline):
    model = OrderItem
    extra = 0


@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    list_display = ('number', 'full_name', 'phone', 'delivery_method', 'payment_method', 'total', 'status', 'paid_at')
    list_filter = ('status', 'delivery_method', 'payment_method')
    search_fields = ('full_name', 'phone', 'email', 'promo_code')
    inlines = [OrderItemInline]


@admin.register(Partner)
class PartnerAdmin(admin.ModelAdmin):
    list_display = ('name', 'site_url', 'is_active')
    list_filter = ('is_active',)
    search_fields = ('name', 'description')


admin.site.register(CompanyProfile)
admin.site.register(CompanyInfo)
admin.site.register(Term)
admin.site.register(Vacancy)
admin.site.register(ProductType)
admin.site.register(Manufacturer)
admin.site.register(Supply)

# Register your models here.

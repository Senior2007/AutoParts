from .cart import Cart
from .models import CompanyProfile
from .timeinfo import base_time_context


def site_context(request):
    return {
        'cart_quantity': len(Cart(request)),
        'site_company': CompanyProfile.objects.first(),
        **base_time_context(),
    }

from decimal import Decimal

from .models import Part

CART_SESSION_KEY = 'cart'
MAX_ITEM_QUANTITY = 99


class Cart:
    def __init__(self, request):
        self.session = request.session
        cart = self.session.get(CART_SESSION_KEY)
        if not isinstance(cart, dict):
            cart = {}
            self.session[CART_SESSION_KEY] = cart
        self.cart = cart
        self._drop_unavailable()

    def _drop_unavailable(self):
        if not self.cart:
            return
        ids = [int(key) for key in self.cart if str(key).isdigit()]
        available = {str(pk) for pk in Part.objects.filter(pk__in=ids, is_active=True).values_list('pk', flat=True)}
        if set(self.cart) != available:
            self.cart = {key: quantity for key, quantity in self.cart.items() if key in available}
            self.save()

    def __iter__(self):
        parts = Part.objects.select_related('product_type', 'manufacturer').filter(pk__in=[int(pk) for pk in self.cart])
        for part in parts:
            quantity = self.cart.get(str(part.pk), 0)
            yield {
                'part': part,
                'quantity': quantity,
                'unit_price': part.price,
                'total_price': part.price * quantity,
                'exceeds_stock': quantity > part.quantity,
            }

    def __len__(self):
        return sum(self.cart.values())

    @property
    def is_empty(self):
        return not self.cart

    def add(self, part, quantity=1, replace=False):
        key = str(part.pk)
        current = self.cart.get(key, 0)
        new_quantity = quantity if replace else current + quantity
        new_quantity = max(1, min(new_quantity, MAX_ITEM_QUANTITY, part.quantity or 1))
        self.cart[key] = new_quantity
        self.save()
        return new_quantity

    def remove(self, part):
        self.cart.pop(str(part.pk), None)
        self.save()

    def clear(self):
        self.session[CART_SESSION_KEY] = {}
        self.cart = self.session[CART_SESSION_KEY]
        self.save()

    def save(self):
        self.session[CART_SESSION_KEY] = self.cart
        self.session.modified = True

    def total(self):
        return sum((row['total_price'] for row in self), Decimal('0.00'))

    def has_stock_problems(self):
        return any(row['exceeds_stock'] for row in self)

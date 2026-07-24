from decimal import Decimal
from .models import Article


class Cart:
    SESSION_KEY = 'cart'

    def __init__(self, request):
        self.session = request.session
        cart = self.session.get(self.SESSION_KEY)
        if cart is None:
            cart = self.session[self.SESSION_KEY] = {}
        self.cart = cart

    def _make_key(self, article_id, size):
        return f"{article_id}:{size or ''}"

    def add(self, article: Article, quantity=1, size=None):
        key = self._make_key(article.id, size)
        item = self.cart.get(key)
        if item:
            item['quantity'] = int(item.get('quantity', 0)) + int(quantity)
        else:
            self.cart[key] = {
                'article_id': article.id,
                'name': article.nom,
                'price': str(article.prix),
                'quantity': int(quantity),
                'size': size or '',
            }
        self.save()

    def remove(self, key):
        if key in self.cart:
            del self.cart[key]
            self.save()

    def update_quantity(self, key, quantity):
        if key in self.cart:
            if quantity <= 0:
                del self.cart[key]
            else:
                self.cart[key]['quantity'] = int(quantity)
            self.save()

    def clear(self):
        self.session[self.SESSION_KEY] = {}
        self.save()

    def save(self):
        self.session.modified = True

    def __iter__(self):
        # Yield items with Decimal price and subtotal
        for key, item in list(self.cart.items()):
            price = Decimal(item['price'])
            quantity = int(item['quantity'])
            yield {
                'key': key,
                'article_id': item['article_id'],
                'name': item['name'],
                'price': price,
                'quantity': quantity,
                'size': item.get('size', ''),
                'subtotal': price * quantity,
            }

    def get_total_price(self):
        total = Decimal('0.00')
        for item in self:
            total += item['subtotal']
        return total

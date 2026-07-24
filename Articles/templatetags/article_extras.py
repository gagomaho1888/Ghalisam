from django import template
from django.contrib.auth.models import User

register = template.Library()

@register.filter
def price_fr(value):
    try:
        number = round(float(value))
        return f"{number:,}".replace(",", ".")
    except (ValueError, TypeError):
        return value

@register.filter
def has_livreur_profile(user):
    try:
        return bool(user.livreur_profile)
    except (AttributeError, User.DoesNotExist):
        return False

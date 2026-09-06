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

@register.filter
def couleur_hex(value):
    colors = {
        'noir': 'linear-gradient(135deg,#1f2937,#374151)',
        'blanc': 'linear-gradient(135deg,#ffffff,#e5e7eb)',
        'rouge': 'linear-gradient(135deg,#dc2626,#f87171)',
        'orange': 'linear-gradient(135deg,#ea580c,#fb923c)',
        'vert': 'linear-gradient(135deg,#16a34a,#4ade80)',
        'bleu': 'linear-gradient(135deg,#2563eb,#60a5fa)',
        'bleu denim': 'linear-gradient(135deg,#1e3a8a,#3b5f8a)',
        'rose': 'linear-gradient(135deg,#db2777,#f472b6)',
        'marron': 'linear-gradient(135deg,#7c2d12,#b45309)',
        'brun': 'linear-gradient(135deg,#7c2d12,#b45309)',
        'gris': 'linear-gradient(135deg,#6b7280,#9ca3af)',
        'gris fonce': 'linear-gradient(135deg,#374151,#4b5563)',
        'violet': 'linear-gradient(135deg,#7c3aed,#a78bfa)',
        'jaune': 'linear-gradient(135deg,#ca8a04,#facc15)',
        'vert kaki': 'linear-gradient(135deg,#4d7c0f,#84cc16)',
        'beige': 'linear-gradient(135deg,#b08968,#d6b9a0)',
        'marine': 'linear-gradient(135deg,#1e3a8a,#312e81)',
    }
    if not value:
        return 'transparent'
    normalized = value.lower().strip()
    if normalized in colors:
        return colors[normalized]
    if 'gris' in normalized:
        return colors['gris']
    if 'marron' in normalized or 'brun' in normalized:
        return colors['marron']
    if 'denim' in normalized:
        return colors['bleu denim']
    if 'vert' in normalized or 'kaki' in normalized:
        return colors['vert']
    if 'bleu' in normalized:
        return colors['bleu']
    if 'blanc' in normalized or 'blanche' in normalized:
        return colors['blanc']
    if 'noir' in normalized:
        return colors['noir']
    if 'rouge' in normalized:
        return colors['rouge']
    if 'orange' in normalized:
        return colors['orange']
    if 'rose' in normalized:
        return colors['rose']
    if 'violet' in normalized:
        return colors['violet']
    if 'jaune' in normalized:
        return colors['jaune']
    return 'transparent'

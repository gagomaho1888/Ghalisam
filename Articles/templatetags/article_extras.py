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

_COULEURS = frozenset((
    'noir', 'blanc', 'rouge', 'orange', 'vert', 'bleu', 'bleu denim',
    'rose', 'marron', 'brun', 'gris', 'gris fonce', 'violet', 'jaune',
    'vert kaki', 'beige', 'marine',
))


def _resoudre_couleur(value):
    """Retourne la cle de couleur canonique, ou None si aucune correspondance."""
    if not value:
        return None
    normalized = value.lower().strip()
    if normalized in _COULEURS:
        return normalized
    for motif, cle in (
        ('gris fonce', 'gris fonce'),
        ('gris', 'gris'),
        ('marron', 'marron'),
        ('brun', 'marron'),
        ('denim', 'bleu denim'),
        ('kaki', 'vert kaki'),
        ('vert', 'vert'),
        ('bleu', 'bleu'),
        ('marine', 'marine'),
        ('blanche', 'blanc'),
        ('blanc', 'blanc'),
        ('noir', 'noir'),
        ('rouge', 'rouge'),
        ('orange', 'orange'),
        ('rose', 'rose'),
        ('violet', 'violet'),
        ('jaune', 'jaune'),
        ('beige', 'beige'),
    ):
        if motif in normalized:
            return cle
    return None


@register.filter
def couleur_class(value):
    """Retourne une classe CSS (couleur-<cle>) au lieu d'un style inline.

    Les declinations sont definies dans static/css/base.css (.couleur-*).
    Le choix d'une classe (et non d'une valeur CSS) permet de rendre les
    pastilles de couleur sans 'unsafe-inline' dans la CSP.
    """
    cle = _resoudre_couleur(value)
    return 'couleur-%s' % cle if cle else 'couleur-inconnue'

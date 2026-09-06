from django.core.cache import cache
from django.utils import timezone


def get_client_ip(request):
    """Retourne l'adresse IP réelle du client, en tenant compte du proxy (nginx).

    En production, Django tourne derrière nginx (`proxy_pass`), donc REMOTE_ADDR
    contient toujours 127.0.0.1. On utilise alors le premier adresse de l'en-tête
    X-Forwarded-For posé par nginx. En dev (DEBUG), il n'y a pas de proxy et
    REMOTE_ADDR est l'adresse du client.
    """
    x_forwarded = request.META.get('HTTP_X_FORWARDED_FOR')
    if x_forwarded:
        # nginx ajoute : <client>, <proxy1>, ...  -> on prend le premier
        return x_forwarded.split(',')[0].strip()
    return request.META.get('REMOTE_ADDR', 'unknown')


def check_rate_limit(key, max_attempts=5, window=900):
    """Vérifie si une clé n'a pas dépassé le nombre d'essais dans la fenêtre."""
    data = cache.get(key)
    if data is None:
        return True
    attempts, first_attempt = data
    if timezone.now().timestamp() - first_attempt > window:
        cache.delete(key)
        return True
    return attempts < max_attempts


def record_attempt(key, window=900):
    """Enregistre un échec pour une clé dans la fenêtre."""
    data = cache.get(key)
    now = timezone.now().timestamp()
    if data is None:
        cache.set(key, (1, now), window)
    else:
        attempts, first_attempt = data
        if now - first_attempt > window:
            cache.set(key, (1, now), window)
        else:
            cache.set(key, (attempts + 1, first_attempt), window)
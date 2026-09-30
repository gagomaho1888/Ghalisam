from django.shortcuts import render
import secrets
from django.conf import settings


def csp_nonce(request):
    """Context processor exposant le nonce CSP aux templates."""
    return {'csp_nonce': getattr(request, 'csp_nonce', '')}


def build_csp_header(policy=None, overrides=None):
    """Génère la politique Content-Security-Policy à partir des settings.

    `overrides` permet d'assouplir ponctuellement une directive (voir
    CSP_ADMIN_POLICY_OVERRIDES pour /admin/).
    """
    pol = policy or settings.CONTENT_SECURITY_POLICY
    if overrides:
        pol = {**pol, **overrides}
    parts = []
    for directive, values in pol.items():
        if not values:
            parts.append(directive)
        else:
            parts.append(f"{directive} {values}")
    return "; ".join(parts)


def get_policy_overrides(request):
    """Retourne les surcharges de directives CSP applicables à cette requête."""
    admin_paths = getattr(settings, 'CSP_ADMIN_PATHS', ())
    if admin_paths and request.path.startswith(admin_paths):
        return getattr(settings, 'CSP_ADMIN_POLICY_OVERRIDES', {})
    return {}


class CSPMiddleware:
    """Ajoute un en-tête Content-Security-Policy strict avec nonce pour les scripts inline."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        request.csp_nonce = secrets.token_urlsafe(24)
        response = self.get_response(request)
        if getattr(settings, 'CSP_ENABLED', False):
            nonce_sources = f"'nonce-{request.csp_nonce}'"
            policy = build_csp_header(overrides=get_policy_overrides(request))
            response['Content-Security-Policy'] = policy.replace('__NONCE__', nonce_sources)
        return response


class Handle404Middleware:
    """Remplace la page d'erreur 404 technique de Django (visible avec DEBUG=True
    pour une URL invalide) par le template 404 stylisé."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)
        if response.status_code == 404 and response.get('Content-Type', '').startswith('text/html'):
            content = response.content[:2000].decode('utf-8', errors='ignore').lower()
            # La page technique 404 de debug contient 'page not found' ou 'page non trouvée'.
            # Notre propre template 404 contient 'page non trouvée - ghalisam'
            if 'ghalisam' not in content:
                return render(request, '404.html', status=404, using='django')
        return response
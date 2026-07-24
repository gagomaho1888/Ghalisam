from functools import wraps
from django.shortcuts import redirect
from django.contrib import messages


def admin_required(view_func):
    @wraps(view_func)
    def wrapper(request, *args, **kwargs):
        if not request.user.is_authenticated:
            return redirect('connexion')
        if not request.user.is_superuser:
            messages.error(request, 'Accès réservé à l\'administrateur.')
            return redirect('acceuil')
        return view_func(request, *args, **kwargs)
    return wrapper


def livreur_required(view_func):
    @wraps(view_func)
    def wrapper(request, *args, **kwargs):
        if not request.user.is_authenticated:
            return redirect('connexion')
        if not hasattr(request.user, 'livreur_profile'):
            messages.error(request, 'Accès réservé aux livreurs.')
            return redirect('acceuil')
        if not request.user.livreur_profile.est_actif:
            messages.error(request, 'Votre compte livreur est désactivé.')
            return redirect('acceuil')
        return view_func(request, *args, **kwargs)
    return wrapper

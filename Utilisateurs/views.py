import secrets
import string
import logging

from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.shortcuts import redirect, render
from django.core.mail import send_mail
from django.utils import timezone
from django.conf import settings
from django.core.cache import cache

from Articles.models import Article
from .models import Commande, Utilisateur

logger = logging.getLogger('Utilisateurs')


RATE_LIMIT_ATTEMPTS = 5
RATE_LIMIT_WINDOW = 900  # 15 minutes


def _check_rate_limit(key, max_attempts=RATE_LIMIT_ATTEMPTS, window=RATE_LIMIT_WINDOW):
    data = cache.get(key)
    if data is None:
        return True
    attempts, first_attempt = data
    if timezone.now().timestamp() - first_attempt > window:
        cache.delete(key)
        return True
    return attempts < max_attempts


def _record_attempt(key, window=RATE_LIMIT_WINDOW):
    data = cache.get(key)
    if data is None:
        cache.set(key, (1, timezone.now().timestamp()), window)
    else:
        attempts, first_attempt = data
        if timezone.now().timestamp() - first_attempt > window:
            cache.set(key, (1, timezone.now().timestamp()), window)
        else:
            cache.set(key, (attempts + 1, first_attempt), window)


def _generer_code():
    alphabet = string.ascii_uppercase + string.digits
    return ''.join(secrets.choice(alphabet) for _ in range(8))


def _envoyer_code(user):
    profil = user.utilisateur
    code = _generer_code()
    profil.code_validation = code
    profil.code_validation_expires = timezone.now() + timezone.timedelta(minutes=10)
    profil.save()

    send_mail(
        subject='Code de vérification - Galisham Boutique',
        message=f'Bonjour {user.first_name},\n\nVotre code de vérification est : {code}\n\nCe code est valide pendant 10 minutes.\n\nGalisham Boutique',
        from_email=settings.EMAIL_HOST_USER,
        recipient_list=[user.email],
        fail_silently=False,
    )


def connexion(request):
    error = None
    if request.method == "POST":
        username = request.POST.get("username", "").strip()
        password = request.POST.get("password", "")

        rl_key = f'login_attempts:{username or "empty"}'
        if not _check_rate_limit(rl_key):
            error = "Trop de tentatives. Réessayez dans 15 minutes."
        elif not username or not password:
            error = "Veuillez remplir tous les champs."
        else:
            user = authenticate(request, username=username, password=password)
            if user is not None:
                cache.delete(rl_key)
                if hasattr(user, 'utilisateur') and not user.utilisateur.email_verified:
                    profil = user.utilisateur
                    if not profil.code_validation or timezone.now() > profil.code_validation_expires:
                        _envoyer_code(user)
                    request.session['verify_user_id'] = user.id
                    return redirect('verifier_email')
                request.session.cycle_key()
                login(request, user)
                return redirect("acceuil")
            _record_attempt(rl_key)
            error = "Mot de passe incorrect ou compte inconnu."

    return render(request, "Utilisateurs/connexion.html", {"error": error})


def inscription(request):
    error = None
    if request.method == "POST":
        username = request.POST.get("username", "").strip()
        first_name = request.POST.get("prenom", "").strip()
        last_name = request.POST.get("nom", "").strip()
        email = request.POST.get("email", "").strip()
        password = request.POST.get("password", "")
        password2 = request.POST.get("password2", "")

        if not username or not first_name or not last_name or not email or not password or not password2:
            error = "Tous les champs sont requis."
        elif password != password2:
            error = "Les mots de passe sont différents."
        elif len(password) < 8:
            error = "Le mot de passe doit contenir au moins 8 caractères."
        elif User.objects.filter(username=username).exists() or User.objects.filter(email=email).exists():
            error = "Compte existant : utilisez un autre nom d'utilisateur ou email."
        else:
            user = User.objects.create_user(
                username=username, email=email, password=password, is_active=True
            )
            user.first_name = first_name
            user.last_name = last_name
            user.save()
            Utilisateur.objects.create(nom=user, prenom=first_name, adresse=email)

            _envoyer_code(user)
            request.session['verify_user_id'] = user.id
            return redirect('verifier_email')

    return render(request, "Utilisateurs/inscription.html", {
        "error": error,
    })


def verifier_email(request):
    user_id = request.session.get('verify_user_id')
    email_display = ''

    if user_id:
        try:
            user = User.objects.get(id=user_id)
            email_display = user.email
        except User.DoesNotExist:
            user_id = None

    error = None

    if request.method == "POST":
        code = request.POST.get("code", "").strip()

        if not code:
            error = "Veuillez entrer le code de vérification."
        else:
            rl_key = f'verify_attempts:{user_id or "none"}'
            if not _check_rate_limit(rl_key):
                error = "Trop de tentatives. Réessayez dans 15 minutes."
            elif not user_id:
                error = "Session expirée. Connectez-vous à nouveau."
            else:
                user_found = None
                profil_found = None

                try:
                    u = User.objects.get(id=user_id)
                    if hasattr(u, 'utilisateur'):
                        user_found = u
                        profil_found = u.utilisateur
                except User.DoesNotExist:
                    pass

                if not user_found or not profil_found:
                    error = "Veuillez réessayer."
                elif profil_found.code_validation != code:
                    _record_attempt(rl_key)
                    error = "Veuillez réessayer."
                elif not profil_found.code_validation_expires or timezone.now() > profil_found.code_validation_expires:
                    error = "Le code a expiré. Demandez un nouveau code."
                else:
                    cache.delete(rl_key)
                    profil_found.email_verified = True
                    profil_found.code_validation = ''
                    profil_found.code_validation_expires = None
                    profil_found.save()
                    if 'verify_user_id' in request.session:
                        del request.session['verify_user_id']
                    request.session.cycle_key()
                    login(request, user_found)
                    return render(request, "Utilisateurs/bienvenue.html", {
                        "prenom": user_found.first_name or user_found.username,
                    })

    return render(request, "Utilisateurs/verifier_email.html", {
        "email": email_display,
        "error": error,
    })


def resend_code(request):
    user_id = request.session.get('verify_user_id')
    if user_id:
        rl_key = f'resend_attempts:{user_id}'
        if not _check_rate_limit(rl_key, max_attempts=3):
            try:
                user = User.objects.get(id=user_id)
                profil = user.utilisateur
                return render(request, "Utilisateurs/verifier_email.html", {
                    "email": user.email,
                    "error": "Trop de demandes. Attendez 15 minutes.",
                })
            except User.DoesNotExist:
                pass
        else:
            _record_attempt(rl_key)
            try:
                user = User.objects.get(id=user_id)
                profil = user.utilisateur
                if not profil.email_verified:
                    _envoyer_code(user)
                    return render(request, "Utilisateurs/verifier_email.html", {
                        "email": user.email,
                        "success": "Un nouveau code a été envoyé.",
                    })
            except User.DoesNotExist:
                pass
    return redirect("connexion")


# ---------------------------------------------------------------------------
# Profil
# ---------------------------------------------------------------------------

@login_required
def profil(request):
    utilisateur = getattr(request.user, "utilisateur", None)
    commandes = Commande.objects.filter(user=request.user).order_by('-created_at')

    delivered_products = []
    for cmd in commandes.filter(statut=Commande.StatutChoices.LIVREE):
        for item in cmd.items.split(";"):
            item = item.strip()
            if not item:
                continue
            parts = item.split(' x')[0].strip()
            article_id = None
            if ':' in parts:
                _, id_part = parts.rsplit(':', 1)
                if id_part.isdigit():
                    article_id = int(id_part)
                    article = Article.objects.filter(id=article_id, disponible=True).first()
                else:
                    article = Article.objects.filter(nom__iexact=parts, disponible=True).first()
            else:
                article = Article.objects.filter(nom__iexact=parts, disponible=True).first()
            if article and article.id not in [p["id"] for p in delivered_products]:
                already_reviewed = article.reviews.filter(user=request.user).exists()
                delivered_products.append({
                    "id": article.id,
                    "nom": article.nom,
                    "slug": article.slug,
                    "image": article.image.url if article.image else None,
                    "ticket": cmd.ticket,
                    "date": cmd.created_at,
                    "already_reviewed": already_reviewed,
                })

    return render(request, "Utilisateurs/profil.html", {
        "utilisateur": utilisateur,
        "commandes": commandes,
        "delivered_products": delivered_products,
    })


@login_required
def deconnexion(request):
    if request.method == 'POST':
        logout(request)
    return redirect("acceuil")


# ---------------------------------------------------------------------------
# Mot de passe oublié
# ---------------------------------------------------------------------------

def mot_de_passe_oublie(request):
    error = None
    success = None
    if request.method == "POST":
        email = request.POST.get("email", "").strip()
        if not email:
            error = "Veuillez entrer votre adresse email."
        else:
            rl_key = f'reset_attempts:{email}'
            if not _check_rate_limit(rl_key):
                error = "Trop de tentatives. Réessayez dans 15 minutes."
            else:
                try:
                    user = User.objects.get(email=email)
                except User.DoesNotExist:
                    user = None

                if user and hasattr(user, 'utilisateur'):
                    _record_attempt(rl_key)
                    code = _generer_code()
                    profil = user.utilisateur
                    profil.code_validation = code
                    profil.code_validation_expires = timezone.now() + timezone.timedelta(minutes=10)
                    profil.save()

                    send_mail(
                        subject='Réinitialisation mot de passe - Galisham Boutique',
                        message=f'Bonjour {user.first_name},\n\nVotre code de réinitialisation est : {code}\n\nCe code est valide pendant 10 minutes.\n\nSi vous n\'avez pas demandé cette réinitialisation, ignorez cet email.\n\nGalisham Boutique',
                        from_email=settings.EMAIL_HOST_USER,
                        recipient_list=[user.email],
                        fail_silently=False,
                    )
                    request.session['reset_user_id'] = user.id
                    return redirect('reinitialiser_mdp')
                else:
                    error = "Aucun compte trouvé avec cet email."

    return render(request, "Utilisateurs/mot_de_passe_oublie.html", {"error": error, "success": success})


def reinitialiser_mdp(request):
    user_id = request.session.get('reset_user_id')
    if not user_id:
        return redirect('mot_de_passe_oublie')

    try:
        user = User.objects.get(id=user_id)
    except User.DoesNotExist:
        return redirect('mot_de_passe_oublie')

    profil = user.utilisateur
    error = None
    step = request.session.get('reset_step', 'code')

    if request.method == "POST":
        if step == 'code':
            code = request.POST.get("code", "").strip()
            if not code:
                error = "Veuillez entrer le code."
            else:
                rl_key = f'reset_verify:{user_id}'
                if not _check_rate_limit(rl_key):
                    error = "Trop de tentatives. Réessayez dans 15 minutes."
                elif profil.code_validation != code:
                    _record_attempt(rl_key)
                    error = "Veuillez réessayer."
                elif not profil.code_validation_expires or timezone.now() > profil.code_validation_expires:
                    error = "Le code a expiré. Ré demandez un nouveau code."
                else:
                    cache.delete(rl_key)
                    request.session['reset_step'] = 'new_password'
                    return render(request, "Utilisateurs/reinitialiser_mdp.html", {
                        "email": user.email,
                        "step": "new_password",
                        "error": None,
                    })
        elif step == 'new_password':
            password = request.POST.get("password", "")
            password2 = request.POST.get("password2", "")
            if not password or not password2:
                error = "Veuillez remplir tous les champs."
            elif password != password2:
                error = "Les mots de passe sont différents."
            elif len(password) < 8:
                error = "Le mot de passe doit contenir au moins 8 caractères."
            else:
                user.set_password(password)
                user.save()
                profil.code_validation = ''
                profil.code_validation_expires = None
                profil.save()
                del request.session['reset_user_id']
                if 'reset_step' in request.session:
                    del request.session['reset_step']
                return render(request, "Utilisateurs/mot_de_passe_reinitialise.html", {
                    "email": user.email,
                })

    return render(request, "Utilisateurs/reinitialiser_mdp.html", {
        "email": user.email,
        "step": step,
        "error": error,
    })

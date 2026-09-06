import hashlib
import hmac
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
from ecommerce.security import get_client_ip, check_rate_limit, record_attempt

logger = logging.getLogger('Utilisateurs')


RATE_LIMIT_ATTEMPTS = 5
RATE_LIMIT_WINDOW = 900  # 15 minutes
LOGIN_IP_MAX_ATTEMPTS = 10  # Essais globaux max par IP sur la fenêtre
LOGIN_USER_IP_MAX_ATTEMPTS = 5  # Essais max pour un even username depuis une même IP


def _check_rate_limit(key, max_attempts=RATE_LIMIT_ATTEMPTS, window=RATE_LIMIT_WINDOW):
    return check_rate_limit(key, max_attempts=max_attempts, window=window)


def _record_attempt(key, window=RATE_LIMIT_WINDOW):
    record_attempt(key, window=window)


def _generer_code():
    return ''.join(secrets.choice(string.digits) for _ in range(6))


def _hasher_code(code):
    # Hash du code lié à la SECRET_KEY pour ne jamais stocker le code en clair.
    return hmac.new(
        settings.SECRET_KEY.encode('utf-8'),
        code.encode('utf-8'),
        hashlib.sha256,
    ).hexdigest()


def _verifier_code(plain_code, hashed_code):
    if not plain_code or not hashed_code:
        return False
    try:
        return hmac.compare_digest(_hasher_code(plain_code), hashed_code)
    except Exception:
        return False


def _envoyer_code(user):
    profil = user.utilisateur
    code = _generer_code()
    profil.code_validation = _hasher_code(code)
    profil.code_validation_expires = timezone.now() + timezone.timedelta(minutes=10)
    profil.save()

    send_mail(
        subject='Code de vérification - Ghalisam Boutique',
        message=f'Bonjour {user.first_name},\n\nVotre code de vérification est : {code}\n\nCe code est valide pendant 10 minutes.\n\nGhalisam Boutique',
        from_email=settings.EMAIL_HOST_USER,
        recipient_list=[user.email],
        fail_silently=False,
    )


def connexion(request):
    error = None
    if request.method == "POST":
        username = request.POST.get("username", "").strip()
        password = request.POST.get("password", "")
        ip = get_client_ip(request)

        rl_key_user_ip = f'login_attempts:{username or "empty"}:{ip}'
        rl_key_ip = f'login_attempts:ip:{ip}'
        if not _check_rate_limit(rl_key_user_ip, max_attempts=LOGIN_USER_IP_MAX_ATTEMPTS):
            error = "Trop de tentatives pour ce compte. Réessayez dans 15 minutes."
        elif not _check_rate_limit(rl_key_ip, max_attempts=LOGIN_IP_MAX_ATTEMPTS):
            error = "Trop de tentatives depuis cette adresse. Réessayez dans 15 minutes."
        elif not username or not password:
            error = "Veuillez remplir tous les champs."
        else:
            user = authenticate(request, username=username, password=password)
            if user is not None:
                cache.delete(rl_key_user_ip)
                cache.delete(rl_key_ip)
                request.session.cycle_key()
                login(request, user)
                return redirect("acceuil")
            _record_attempt(rl_key_user_ip)
            _record_attempt(rl_key_ip)
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

        ip = get_client_ip(request)
        rl_key = f'inscription_attempts:{ip}'
        if not _check_rate_limit(rl_key, max_attempts=5, window=3600):
            error = "Trop de tentatives d'inscription depuis cette adresse. Réessayez plus tard."
        elif not username or not first_name or not last_name or not email or not password or not password2:
            error = "Tous les champs sont requis."
        elif password != password2:
            error = "Les mots de passe sont différents."
        elif len(password) < 8:
            error = "Le mot de passe doit contenir au moins 8 caractères."
        elif User.objects.filter(username=username).exists() or User.objects.filter(email=email).exists():
            _record_attempt(rl_key, window=3600)
            error = "Nom d'utilisateur ou email déjà utilisé."
        else:
            code = _generer_code()
            request.session['pending_user'] = {
                'username': username,
                'first_name': first_name,
                'last_name': last_name,
                'email': email,
                'password': password,
                'code_validation': _hasher_code(code),
                'code_validation_expires': (timezone.now() + timezone.timedelta(minutes=10)).isoformat(),
            }

            send_mail(
                subject='Code de vérification - Ghalisam Boutique',
                message=f'Bonjour {first_name},\n\nVotre code de vérification est : {code}\n\nCe code est valide pendant 10 minutes.\n\nGhalisam Boutique',
                from_email=settings.EMAIL_HOST_USER,
                recipient_list=[email],
                fail_silently=False,
            )
            return redirect('verifier_email')

    return render(request, "Utilisateurs/inscription.html", {
        "error": error,
    })


def verifier_email(request):
    pending = request.session.get('pending_user')
    user_id = request.session.get('verify_user_id')
    email_display = ''

    if pending:
        email_display = pending.get('email', '')
    elif user_id:
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
            if pending:
                expires = timezone.datetime.fromisoformat(pending['code_validation_expires'])
                if timezone.is_naive(expires):
                    expires = timezone.make_aware(expires)
                rl_key = f'verify_attempts_pending:{pending["email"]}'
                if not _check_rate_limit(rl_key):
                    error = "Trop de tentatives. Réessayez dans 15 minutes."
                elif not _verifier_code(code, pending['code_validation']):
                    _record_attempt(rl_key)
                    error = "Code incorrect. Veuillez réessayer."
                elif timezone.now() > expires:
                    error = "Le code a expiré. Demandez un nouveau code."
                else:
                    cache.delete(rl_key)
                    user = User.objects.create_user(
                        username=pending['username'],
                        email=pending['email'],
                        password=pending['password'],
                        is_active=True,
                    )
                    user.first_name = pending['first_name']
                    user.last_name = pending['last_name']
                    user.save()
                    Utilisateur.objects.create(
                        nom=user,
                        prenom=pending['first_name'],
                        adresse='',
                        email_verified=True,
                    )
                    del request.session['pending_user']
                    request.session.cycle_key()
                    login(request, user)
                    return render(request, "Utilisateurs/bienvenue.html", {
                        "prenom": user.first_name or user.username,
                    })
            elif user_id:
                rl_key = f'verify_attempts:{user_id}'
                if not _check_rate_limit(rl_key):
                    error = "Trop de tentatives. Réessayez dans 15 minutes."
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
                    elif not _verifier_code(code, profil_found.code_validation):
                        _record_attempt(rl_key)
                        error = "Code incorrect. Veuillez réessayer."
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
    pending = request.session.get('pending_user')
    user_id = request.session.get('verify_user_id')

    if pending:
        rl_key = f'resend_attempts_pending:{pending["email"]}'
        if not _check_rate_limit(rl_key, max_attempts=3):
            return render(request, "Utilisateurs/verifier_email.html", {
                "email": pending['email'],
                "error": "Trop de demandes. Attendez 15 minutes.",
            })
        _record_attempt(rl_key)
        code = _generer_code()
        expires = (timezone.now() + timezone.timedelta(minutes=10)).isoformat()
        pending['code_validation'] = _hasher_code(code)
        pending['code_validation_expires'] = expires
        request.session['pending_user'] = pending
        send_mail(
            subject='Code de vérification - Ghalisam Boutique',
            message=f'Bonjour {pending["first_name"]},\n\nVotre code de vérification est : {code}\n\nCe code est valide pendant 10 minutes.\n\nGhalisam Boutique',
            from_email=settings.EMAIL_HOST_USER,
            recipient_list=[pending['email']],
            fail_silently=False,
        )
        return render(request, "Utilisateurs/verifier_email.html", {
            "email": pending['email'],
            "success": "Un nouveau code a été envoyé.",
        })

    if user_id:
        rl_key = f'resend_attempts:{user_id}'
        if not _check_rate_limit(rl_key, max_attempts=3):
            try:
                user = User.objects.get(id=user_id)
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
            if article:
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
                    profil.code_validation = _hasher_code(code)
                    profil.code_validation_expires = timezone.now() + timezone.timedelta(minutes=10)
                    profil.save()

                    send_mail(
                        subject='Réinitialisation mot de passe - Ghalisam Boutique',
                        message=f'Bonjour {user.first_name},\n\nVotre code de réinitialisation est : {code}\n\nCe code est valide pendant 10 minutes.\n\nSi vous n\'avez pas demandé cette réinitialisation, ignorez cet email.\n\nGhalisam Boutique',
                        from_email=settings.EMAIL_HOST_USER,
                        recipient_list=[user.email],
                        fail_silently=False,
                    )
                    request.session['reset_user_id'] = user.id
                    return redirect('reinitialiser_mdp')
                else:
                    # Timing identique (envoi simulé) pour empêcher l'énumération de comptes par mesure du temps de réponse.
                    import time
                    time.sleep(1.5)
                    # Message générique pour ne pas révéler si l'email existe.
                    error = "Si un compte est associé à cet email, un code de réinitialisation a été envoyé."

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
                elif not _verifier_code(code, profil.code_validation):
                    _record_attempt(rl_key)
                    error = "Veuillez réessayer."
                elif not profil.code_validation_expires or timezone.now() > profil.code_validation_expires:
                    error = "Le code a expiré. Ré demandez un nouveau code."
                else:
                    cache.delete(rl_key)
                    request.session.cycle_key()
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

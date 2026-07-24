import math
import logging
import requests
from decimal import Decimal
from django.shortcuts import render, get_object_or_404, redirect
from django.core.paginator import Paginator
from django.db.models import Q, Avg, Count, F
from django.db import transaction
from django.contrib.postgres.search import TrigramSimilarity
from django.http import JsonResponse
from django.contrib.auth.decorators import login_required
from django.views.decorators.http import require_POST
from django.core.files.storage import default_storage
from .models import Article, ArticleVariant, NewsletterSubscriber, Review
from .forms import ReviewForm
from django.urls import reverse
from .cart import Cart
from uuid import uuid4
from django.contrib import messages
from django.core.validators import validate_email
from django.core.exceptions import ValidationError
from django.views.decorators.cache import cache_page
from django.core.cache import cache
from Utilisateurs.models import Commande

logger = logging.getLogger('Articles')


REVIEWS_PER_PAGE = 5


def user_has_purchased(user, article):
    commandes = Commande.objects.filter(
        user=user,
        statut=Commande.StatutChoices.LIVREE
    )
    article_id_str = str(article.id)
    article_name = article.nom.lower().strip()
    for cmd in commandes:
        for item in cmd.items.split(';'):
            item = item.strip()
            if not item:
                continue
            if f':{article_id_str} ' in item or item.endswith(f':{article_id_str}'):
                return True
            item_name = item.split(' x')[0].strip().lower()
            if item_name == article_name:
                return True
    return False


def get_review_stats(article):
    stats = Review.objects.filter(article=article).aggregate(
        avg_rating=Avg('rating'),
        total=Count('id')
    )
    avg_rating = stats['avg_rating'] or 0
    total = stats['total'] or 0

    distribution_raw = Review.objects.filter(article=article).values('rating').annotate(
        count=Count('id')
    )
    count_by_rating = {r['rating']: r['count'] for r in distribution_raw}
    distribution = []
    for i in range(5, 0, -1):
        count = count_by_rating.get(i, 0)
        pct = round((count / total * 100)) if total > 0 else 0
        distribution.append({'stars': i, 'count': count, 'pct': pct})
    return {
        'avg_rating': round(float(avg_rating), 1),
        'total': total,
        'distribution': distribution,
    }


def acceuil(request):
    articles = Article.objects.filter(disponible=True).prefetch_related('variantes')
    articles = articles[:6]  # Limiter à 6 articles
    checkout_ticket = request.session.pop('checkout_ticket', None)
    return render(request, 'Articles/acceuil.html', {'articles': articles, 'checkout_ticket': checkout_ticket})


def produit_list(request):
    articles = Article.objects.filter(disponible=True).prefetch_related('variantes')
    query = request.GET.get('q', '').strip()
    if query:
        try:
            articles = articles.annotate(
                similarity=(
                    TrigramSimilarity('nom', query) + TrigramSimilarity('description', query)
                )
            ).filter(similarity__gt=0.15).order_by('-similarity')
        except Exception as e:
            logger.warning("Trigram search failed, falling back to icontains: %s", e)
            articles = articles.filter(
                Q(nom__icontains=query) | Q(description__icontains=query)
            )
    paginator = Paginator(articles, 8)
    page_number = request.GET.get('page', 1)
    page_obj = paginator.get_page(page_number)
    return render(request, 'Articles/produit_list.html', {'page_obj': page_obj, 'articles': page_obj.object_list, 'query': query})


def produit_detail(request, article_id):
    article = get_object_or_404(
        Article.objects.prefetch_related('variantes', 'reviews__user', 'reviews__user__utilisateur'),
        id=article_id, disponible=True
    )
    available_variants = article.variantes.filter(stock__gt=0)

    can_review = False
    existing_review = None
    if request.user.is_authenticated:
        can_review = user_has_purchased(request.user, article)
        try:
            existing_review = Review.objects.get(user=request.user, article=article)
        except Review.DoesNotExist:
            pass

    all_reviews = article.reviews.select_related('user__utilisateur').all()
    if existing_review:
        all_reviews = all_reviews.exclude(id=existing_review.id)
    reviews_page = request.GET.get('reviews_page', 1)
    paginator = Paginator(all_reviews, REVIEWS_PER_PAGE)
    reviews_page_obj = paginator.get_page(reviews_page)

    stats = get_review_stats(article)
    form = ReviewForm()

    return render(request, 'Articles/produit_detail.html', {
        'article': article,
        'available_variants': available_variants,
        'can_review': can_review,
        'existing_review': existing_review,
        'reviews': reviews_page_obj,
        'stats': stats,
        'form': form,
        'message': None,
    })


def add_to_cart(request):
    if not request.user.is_authenticated:
        return redirect('connexion')
    if request.method == 'POST':
        article_id = request.POST.get('article_id')
        try:
            quantity = int(request.POST.get('quantity', 1))
        except ValueError:
            quantity = 1
        if quantity <= 0:
            quantity = 1
        size = request.POST.get('size', '')
        article = get_object_or_404(Article.objects.prefetch_related('variantes'), id=article_id, disponible=True)
        variant = article.variantes.filter(taille=size).first() if size else None

        if variant:
            stock_in_cart = 0
            cart = Cart(request)
            key = cart._make_key(article.id, size)
            if key in cart.cart:
                stock_in_cart = int(cart.cart[key].get('quantity', 0))
            available_stock = variant.stock - stock_in_cart
        else:
            stock_in_cart = 0
            cart = Cart(request)
            key = cart._make_key(article.id, size)
            if key in cart.cart:
                stock_in_cart = int(cart.cart[key].get('quantity', 0))
            available_stock = article.stock - stock_in_cart

        if available_stock <= 0:
            messages.warning(request, 'Ce produit est épuisé pour la taille sélectionnée.')
            return redirect('produit_detail', article_id=article_id)

        if quantity > available_stock:
            messages.warning(
                request,
                f'Stock insuffisant. Veuillez réduire votre quantité (stock restant : {available_stock}).'
            )
            return redirect('produit_detail', article_id=article_id)

        cart.add(article, quantity=quantity, size=size)
        return redirect('commande')
    return redirect(request.META.get('HTTP_REFERER', reverse('produit_list')))


def _calculer_frais_livraison(distance_km):
    if distance_km <= 10:
        return Decimal('1000')
    if distance_km <= 50:
        return Decimal('1500')
    if distance_km <= 200:
        return Decimal('2500')
    if distance_km <= 500:
        return Decimal('4000')
    return Decimal('5000')


def commande(request):
    cart = Cart(request)
    delivery = {
        'ville': '',
        'pays': '',
        'code_postal': '',
        'telephone': '',
    }
    is_guest = not request.user.is_authenticated
    if request.user.is_authenticated:
        utilisateur = getattr(request.user, 'utilisateur', None)
        if utilisateur:
            delivery.update({
                'ville': utilisateur.ville,
                'pays': utilisateur.pays,
                'code_postal': utilisateur.code_postal,
                'telephone': utilisateur.telephone,
            })
    if request.method == 'POST' and request.POST.get('action') == 'checkout':
        if is_guest:
            return redirect('connexion')
        if not cart.cart:
            messages.warning(request, 'Votre panier est vide.')
            return redirect('produit_list')
        delivery = {
            'ville': request.POST.get('ville', ''),
            'pays': request.POST.get('pays', ''),
            'code_postal': request.POST.get('code_postal', ''),
            'telephone': request.POST.get('telephone', ''),
        }

        try:
            lat = Decimal(request.POST.get('lat', '0'))
            lon = Decimal(request.POST.get('lon', '0'))
        except Exception:
            lat = Decimal('0')
            lon = Decimal('0')

        if lat == 0 and lon == 0:
            frais_livraison = Decimal('1500')
        else:
            shop_lat = Decimal('5.3600')
            shop_lon = Decimal('-4.0083')
            R = Decimal('6371')
            d_lat = math.radians(float(lat - shop_lat))
            d_lon = math.radians(float(lon - shop_lon))
            a = (math.sin(d_lat / 2) ** 2
                 + math.cos(math.radians(float(shop_lat)))
                 * math.cos(math.radians(float(lat)))
                 * math.sin(d_lon / 2) ** 2)
            distance_km = float(R * 2 * Decimal(str(math.atan2(math.sqrt(a), math.sqrt(1 - a)))))
            frais_livraison = _calculer_frais_livraison(distance_km)

        total = cart.get_total_price()
        total += frais_livraison
        ticket_code = f"TKT-{uuid4().hex[:8].upper()}"
        if request.user.is_authenticated:
            item_descriptions = []
            cart_items_data = []
            for item in cart:
                size = item['size'] or ''
                article = get_object_or_404(Article, id=item['article_id'], disponible=True)
                if size:
                    variant = article.variantes.filter(taille=size).first()
                else:
                    variant = None

                db_stock = variant.stock if variant else article.stock
                if item['quantity'] > db_stock:
                    message = f"Le stock est insuffisant pour {article.nom} {size or ''}."
                    return render(request, 'Articles/commande.html', {
                        'cart': cart,
                        'delivery': delivery,
                        'message': message,
                        'total': total,
                        'is_guest': is_guest,
                    })

                item_descriptions.append(f"{item['name']}:{article.id} x{item['quantity']} ({size or 'sans taille'})")
                cart_items_data.append((article, variant, item['quantity']))

            total_recalcule = sum(
                (item[0].prix * item[2]) for item in cart_items_data
            ) + frais_livraison

            try:
                with transaction.atomic():
                    for article, variant, qty in cart_items_data:
                        if variant:
                            updated = ArticleVariant.objects.filter(
                                id=variant.id, stock__gte=qty
                            ).update(stock=F('stock') - qty)
                            if not updated:
                                raise ValueError(f"Stock insuffisant pour {article.nom} {variant.taille}")
                        else:
                            updated = Article.objects.filter(
                                id=article.id, stock__gte=qty
                            ).update(stock=F('stock') - qty)
                            if not updated:
                                raise ValueError(f"Stock insuffisant pour {article.nom}")

                    Commande.objects.create(
                        user=request.user,
                        ticket=ticket_code,
                        fullname=request.user.get_full_name() or request.user.username,
                        adresse=delivery['ville'],
                        ville=delivery['ville'],
                        pays=delivery['pays'],
                        code_postal=delivery['code_postal'],
                        telephone=delivery['telephone'],
                        total_price=total_recalcule,
                        shipping_cost=frais_livraison,
                        items='; '.join(item_descriptions),
                    )
            except ValueError as e:
                messages.warning(request, str(e))
                return redirect('commande')

            request.session['checkout_ticket'] = ticket_code
            cart.clear()
            return redirect('acceuil')
        message = 'Connectez-vous pour enregistrer votre ticket dans votre profil.'
        return render(request, 'Articles/commande.html', {'cart': cart, 'delivery': delivery, 'message': message, 'total': total})

    total = cart.get_total_price()
    return render(request, 'Articles/commande.html', {'cart': cart, 'delivery': delivery, 'total': total, 'is_guest': is_guest})


def update_cart(request):
    if not request.user.is_authenticated:
        return redirect('connexion')
    if request.method == 'POST':
        key = request.POST.get('key')
        action = request.POST.get('action')
        cart = Cart(request)
        if key and action:
            current = cart.cart.get(key)
            if not current:
                return redirect('commande')
            qty = int(current.get('quantity', 1))
            if action == 'increment':
                article_id = current.get('article_id')
                size = current.get('size', '')
                article = get_object_or_404(Article, id=article_id, disponible=True)
                variant = article.variantes.filter(taille=size).first() if size else None
                available_stock = variant.stock if variant else article.stock
                if qty + 1 <= available_stock:
                    cart.update_quantity(key, qty + 1)
                else:
                    messages.warning(request, f'Stock insuffisant pour {article.nom}. Veuillez réduire votre quantité.')
            elif action == 'decrement':
                cart.update_quantity(key, qty - 1)
            elif action == 'remove':
                cart.remove(key)
            elif action == 'set':
                try:
                    new_q = int(request.POST.get('quantity', 1))
                except ValueError:
                    new_q = qty
                cart.update_quantity(key, new_q)
    return redirect('commande')


def remove_from_cart(request):
    if not request.user.is_authenticated:
        return redirect('connexion')
    if request.method == 'POST':
        key = request.POST.get('key')
        cart = Cart(request)
        if key:
            cart.remove(key)
    return redirect('commande')


def newsletter_subscribe(request):
    if request.method == 'POST':
        email = request.POST.get('email', '').strip()
        if email:
            try:
                validate_email(email)
            except ValidationError:
                messages.error(request, 'Veuillez entrer un email valide.')
                return redirect('acceuil')
            if NewsletterSubscriber.objects.filter(email=email).exists():
                messages.info(request, 'Cet email est déjà inscrit à la newsletter.')
            else:
                NewsletterSubscriber.objects.create(email=email)
                messages.success(request, 'Inscription réussie ! Merci.')
        else:
            messages.error(request, 'Veuillez entrer un email valide.')
    return redirect('acceuil')


@login_required
@require_POST
def add_review(request, article_id):
    article = get_object_or_404(Article, id=article_id, disponible=True)

    if not user_has_purchased(request.user, article):
        messages.error(request, 'Vous ne pouvez laisser un avis qu\'après avoir reçu votre commande.')
        return redirect('produit_detail', article_id=article_id)

    if Review.objects.filter(user=request.user, article=article).exists():
        messages.error(request, 'Vous avez déjà laissé un avis sur ce produit.')
        return redirect('produit_detail', article_id=article_id)

    form = ReviewForm(request.POST, request.FILES)
    if form.is_valid():
        review = form.save(commit=False)
        review.user = request.user
        review.article = article
        review.achat_verifie = True
        review.save()
        messages.success(request, 'Votre avis a été publié avec succès !')
    else:
        for field, errors in form.errors.items():
            for error in errors:
                messages.error(request, f'{error}')

    return redirect('produit_detail', article_id=article_id)


@login_required
@require_POST
def edit_review(request, review_id):
    review = get_object_or_404(Review, id=review_id, user=request.user)

    if not user_has_purchased(request.user, review.article):
        messages.error(request, 'Vous ne pouvez pas modifier cet avis.')
        return redirect('produit_detail', article_id=review.article.id)

    form = ReviewForm(request.POST, request.FILES, instance=review)
    if form.is_valid():
        form.save()
        messages.success(request, 'Votre avis a été modifié avec succès !')
    else:
        for field, errors in form.errors.items():
            for error in errors:
                messages.error(request, f'{error}')

    return redirect('produit_detail', article_id=review.article.id)


@login_required
@require_POST
def delete_review(request, review_id):
    review = get_object_or_404(Review, id=review_id, user=request.user)
    article_id = review.article.id
    if review.image:
        if default_storage.exists(review.image.name):
            default_storage.delete(review.image.name)
    review.delete()
    messages.success(request, 'Votre avis a été supprimé.')
    return redirect('produit_detail', article_id=article_id)


def get_reviews(request, article_id):
    article = get_object_or_404(Article, id=article_id)
    page = request.GET.get('page', 1)
    reviews_qs = Review.objects.filter(article=article).select_related('user__utilisateur')
    paginator = Paginator(reviews_qs, REVIEWS_PER_PAGE)
    page_obj = paginator.get_page(page)

    data = {
        'reviews': [
            {
                'id': r.id,
                'user_name': r.user.username,
                'user_initial': (r.user.first_name or r.user.username)[0].upper(),
                'rating': r.rating,
                'comment': r.comment,
                'image_url': r.image.url if r.image else None,
                'achat_verifie': r.achat_verifie,
                'seller_response': r.seller_response or None,
                'created_at': r.created_at.strftime('%d/%m/%Y'),
            }
            for r in page_obj
        ],
        'has_next': page_obj.has_next(),
        'next_page': page_obj.next_page_number() if page_obj.has_next() else None,
        'total': paginator.count,
        'stats': get_review_stats(article),
    }
    return JsonResponse(data)


# ---------------------------------------------------------------------------
# Géolocalisation – proxy Nominatim
# ---------------------------------------------------------------------------

NOMINIM_URL = "https://nominatim.openstreetmap.org"
HEADERS = {"User-Agent": "GalishamBoutique/1.0 (ecommerce)"}
GEOCODE_CACHE_TTL = 60 * 60  # 1 heure


@cache_page(GEOCODE_CACHE_TTL)
def geocode_search(request):
    q = request.GET.get("q", "").strip()
    if len(q) < 3:
        return JsonResponse({"error": "Requête trop courte"}, status=400)
    try:
        resp = requests.get(
            f"{NOMINIM_URL}/search",
            params={
                "format": "json", "q": q, "limit": 5,
                "accept-language": "fr", "addressdetails": 1,
            },
            headers=HEADERS,
            timeout=10,
        )
        resp.raise_for_status()
        return JsonResponse(resp.json(), safe=False)
    except requests.RequestException:
        return JsonResponse({"error": "Service indisponible"}, status=503)


@cache_page(GEOCODE_CACHE_TTL)
def geocode_reverse(request):
    lat = request.GET.get("lat", "").strip()
    lon = request.GET.get("lon", "").strip()
    if not lat or not lon:
        return JsonResponse({"error": "lat et lon requis"}, status=400)
    try:
        resp = requests.get(
            f"{NOMINIM_URL}/reverse",
            params={
                "format": "json", "lat": lat, "lon": lon,
                "accept-language": "fr", "addressdetails": 1,
            },
            headers=HEADERS,
            timeout=10,
        )
        resp.raise_for_status()
        return JsonResponse(resp.json())
    except requests.RequestException:
        return JsonResponse({"error": "Service indisponible"}, status=503)


def faq(request):
    return render(request, "Articles/faq.html")


def contact(request):
    sent = False
    error = None
    if request.method == "POST":
        fullname = request.POST.get("fullname", "").strip()
        email = request.POST.get("email", "").strip()
        subject = request.POST.get("subject", "").strip()
        message = request.POST.get("message", "").strip()

        if not fullname or not email or not subject or not message:
            error = "Tous les champs sont requis."
        else:
            try:
                validate_email(email)
            except ValidationError:
                error = "Adresse email invalide."
                return render(request, "Articles/contact.html", {"sent": sent, "error": error})

            rl_key = f'contact:{request.META.get("REMOTE_ADDR", "unknown")}'
            from django.core.cache import cache as _cache
            if _cache.get(rl_key):
                error = "Trop de messages. Réessayez dans quelques minutes."
                return render(request, "Articles/contact.html", {"sent": sent, "error": error})
            _cache.set(rl_key, True, 300)

            subject_labels = {
                "commande": "Commande",
                "livraison": "Livraison",
                "retour": "Retour / Échange",
                "produit": "Produit",
                "partenariat": "Partenariat",
                "autre": "Autre",
            }
            label = subject_labels.get(subject, "Autre")
            fullname = fullname[:200]
            message = message[:5000]

            send_mail(
                subject=f"[Contact] {label} - {fullname}",
                message=f"Nom : {fullname}\nEmail : {email}\nSujet : {label}\n\n{message}",
                from_email=settings.EMAIL_HOST_USER,
                recipient_list=[settings.EMAIL_HOST_USER],
                fail_silently=False,
            )
            sent = True

    return render(request, "Articles/contact.html", {"sent": sent, "error": error})


def livraison_retours(request):
    return render(request, "Articles/livraison_retours.html")


def cgu(request):
    return render(request, "Articles/cgu.html")


def cgv(request):
    return render(request, "Articles/cgv.html")


def cookies(request):
    return render(request, "Articles/cookies.html")


def mentions_legales(request):
    return render(request, "Articles/mentions_legales.html")


def cookie_consent(request):
    if request.method == 'POST':
        consent = request.POST.get('consent', '')
        if consent in ('accepted', 'rejected'):
            response = JsonResponse({'status': 'ok'})
            response.set_cookie(
                'cookie_consent', consent,
                max_age=365 * 24 * 60 * 60,
                httponly=False,
                secure=not settings.DEBUG,
                samesite='Lax',
            )
            return response
    return JsonResponse({'status': 'error'}, status=400)


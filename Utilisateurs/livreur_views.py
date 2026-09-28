import logging
import re

from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.core.mail import send_mail
from django.core.paginator import Paginator
from django.db import transaction
from django.db.models import F
from django.template.loader import render_to_string
from django.conf import settings
from django.utils.http import url_has_allowed_host_and_scheme
from Articles.models import Article, ArticleVariant
from .models import Commande, Livreur, Notification
from .decorators import livreur_required

logger = logging.getLogger('Utilisateurs')


def _envoyer_email_livraison(commande):
    try:
        prenom = commande.user.first_name or commande.user.username
        html_message = render_to_string('Articles/email_livraison.html', {
            'prenom': prenom,
            'ticket': commande.ticket,
            'site_url': f'{settings.ALLOWED_HOSTS[0] if settings.ALLOWED_HOSTS else "http://127.0.0.1:8000"}',
        })
        send_mail(
            subject='Votre commande a été livrée - Ghalisam Boutique',
            message=f"Bonjour {prenom},\n\nVotre commande #{commande.ticket} a été livrée avec succès. Merci pour votre confiance !\n\nN'hésitez pas à commenter les articles reçus.\n\nGhalisam Boutique",
            from_email=settings.EMAIL_HOST_USER,
            recipient_list=[commande.user.email],
            html_message=html_message,
            fail_silently=True,
        )
    except Exception as e:
        logger.error("Échec envoi email livraison pour %s : %s", commande.ticket, e)


def _signaler_echec_livraison(commande):
    destinataire = commande.user
    Notification.objects.create(
        livreur=destinataire,
        commande=commande,
        message=(
            f'La livraison de la commande {commande.ticket} a échoué. '
            'Nous contactons un nouveau livreur.'
        ),
    )
    try:
        prenom = destinataire.first_name or destinataire.username
        send_mail(
            subject='Livraison reportée - Ghalisam Boutique',
            message=(
                f"Bonjour {prenom},\n\n"
                f"Nous n'avons pas pu vous livrer la commande #{commande.ticket}.\n"
                "Un nouveau livreur vous contactera rapidement pour convenir d'un nouvel essai.\n\n"
                "Merci de votre compréhension.\n\nGhalisam Boutique"
            ),
            from_email=settings.EMAIL_HOST_USER,
            recipient_list=[destinataire.email],
            fail_silently=True,
        )
    except Exception as e:
        logger.error("Échec envoi email échec livraison pour %s : %s", commande.ticket, e)


@livreur_required
def livreur_dashboard(request):
    page = request.GET.get('page', 1)
    livreur = request.user.livreur_profile
    livreur.marquer_indisponible_si_occupe()
    commandes = Commande.objects.filter(
        livreur=request.user
    ).select_related('user').order_by('-created_at')
    en_attente = commandes.filter(statut=Commande.StatutChoices.EN_ATTENTE).count()
    livrees = commandes.filter(statut=Commande.StatutChoices.LIVREE).count()
    echouees = commandes.filter(statut=Commande.StatutChoices.LIVRAISON_ECHOUEE).count()
    paginator = Paginator(commandes, 20)
    page_obj = paginator.get_page(page)
    return render(request, 'Utilisateurs/livreur_dashboard.html', {
        'commandes': page_obj,
        'en_attente': en_attente,
        'livrees': livrees,
        'echouees': echouees,
        'livreur': livreur,
    })


@livreur_required
def livreur_commandes(request):
    statut = request.GET.get('statut', '')
    page = request.GET.get('page', 1)
    livreur = request.user.livreur_profile
    livreur.marquer_indisponible_si_occupe()
    commandes = Commande.objects.filter(
        livreur=request.user
    ).select_related('user').order_by('-created_at')
    if statut:
        commandes = commandes.filter(statut=statut)
    paginator = Paginator(commandes, 20)
    page_obj = paginator.get_page(page)
    return render(request, 'Utilisateurs/livreur_commandes.html', {
        'commandes': page_obj,
        'statut_selectionne': statut,
        'livreur': livreur,
    })


@livreur_required
def livreur_disponibilite(request):
    livreur = request.user.livreur_profile
    if request.method == 'POST':
        if livreur.a_commande_en_cours:
            livreur.marquer_indisponible_si_occupe()
            messages.info(
                request,
                f'Vous avez {livreur.nb_commandes_en_cours} commande'
                f'{"s" if livreur.nb_commandes_en_cours > 1 else ""} en cours : '
                'vous restez marqué indisponible jusqu’à leur clôture.'
            )
        else:
            livreur.est_disponible = not livreur.est_disponible
            livreur.save(update_fields=['est_disponible'])
            if livreur.est_disponible:
                messages.success(
                    request,
                    'Vous êtes disponible : l’administration peut vous attribuer '
                    'de nouvelles commandes.'
                )
            else:
                messages.warning(
                    request,
                    'Vous êtes indisponible : aucune nouvelle commande ne vous '
                    'sera attribuée. Vos commandes en cours restent actives.'
                )
        destination = request.POST.get('next') or request.META.get('HTTP_REFERER')
        if destination and url_has_allowed_host_and_scheme(
            destination, allowed_hosts={request.get_host()}, require_https=request.is_secure()
        ):
            return redirect(destination)
        return redirect('livreur_dashboard')
    return redirect('livreur_dashboard')


def _decrementer_stock(commande):
    try:
        with transaction.atomic():
            for part in commande.items.split(';'):
                part = part.strip()
                if not part:
                    continue
                match = re.search(r':(\d+)\s+x(\d+)\s+\((.+?)\)', part)
                if not match:
                    continue
                article_id = int(match.group(1))
                qty = int(match.group(2))
                taille = match.group(3).strip()
                if taille and taille != 'sans taille':
                    variant = ArticleVariant.objects.filter(
                        article_id=article_id, taille=taille, stock__gte=qty
                    ).first()
                    if variant:
                        ArticleVariant.objects.filter(
                            id=variant.id, stock__gte=qty
                        ).update(stock=F('stock') - qty)
                    else:
                        logger.warning("Variante introuvable: article=%s taille=%s", article_id, taille)
                else:
                    updated = Article.objects.filter(
                        id=article_id, stock__gte=qty
                    ).update(stock=F('stock') - qty)
                    if not updated:
                        logger.warning("Stock insuffisant pour article %s", article_id)
    except Exception as e:
        logger.error("Erreur décrementation stock pour %s : %s", commande.ticket, e)


@livreur_required
def livreur_update_status(request, commande_id):
    commande = get_object_or_404(Commande, id=commande_id, livreur=request.user)
    if request.method == 'POST':
        nouveau_statut = request.POST.get('statut')
        transitions_valides = Commande.TRANSITIONS_LIVREUR.get(commande.statut, [])
        if nouveau_statut in transitions_valides:
            commande.statut = nouveau_statut
            commande.save(update_fields=['statut'])
            request.user.livreur_profile.marquer_disponible_si_libre()
            messages.success(request, f'Statut mis à jour : {commande.get_statut_display()}.')

            if nouveau_statut == Commande.StatutChoices.LIVREE:
                _decrementer_stock(commande)
                _envoyer_email_livraison(commande)
            elif nouveau_statut == Commande.StatutChoices.LIVRAISON_ECHOUEE:
                _signaler_echec_livraison(commande)
                messages.warning(
                    request,
                    f'Commande {commande.ticket} signalée comme non livrée : '
                    'le client a été prévenu et l’administration va la réattribuer.'
                )
        else:
            messages.error(request, 'Transition de statut invalide.')
        destination = request.POST.get('next')
        if destination and url_has_allowed_host_and_scheme(
            destination, allowed_hosts={request.get_host()}, require_https=request.is_secure()
        ):
            return redirect(destination)
        return redirect('livreur_commandes')
    return redirect('livreur_commandes')

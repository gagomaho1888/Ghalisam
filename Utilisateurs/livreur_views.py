import logging

from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.core.mail import send_mail
from django.core.paginator import Paginator
from django.template.loader import render_to_string
from django.conf import settings
from .models import Commande
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
            subject='Votre commande a été livrée - Galisham Boutique',
            message=f"Bonjour {prenom},\n\nVotre commande #{commande.ticket} a été livrée avec succès. Merci pour votre confiance !\n\nN'hésitez pas à commenter les articles reçus.\n\nGalisham Boutique",
            from_email=settings.EMAIL_HOST_USER,
            recipient_list=[commande.user.email],
            html_message=html_message,
            fail_silently=True,
        )
    except Exception as e:
        logger.error("Échec envoi email livraison pour %s : %s", commande.ticket, e)


@livreur_required
def livreur_dashboard(request):
    page = request.GET.get('page', 1)
    commandes = Commande.objects.filter(
        livreur=request.user
    ).select_related('user').order_by('-created_at')
    en_attente = commandes.filter(statut='en_attente').count()
    en_preparation = commandes.filter(statut='en_preparation').count()
    en_livraison = commandes.filter(statut='en_livraison').count()
    livrees = commandes.filter(statut='livree').count()
    paginator = Paginator(commandes, 20)
    page_obj = paginator.get_page(page)
    return render(request, 'Utilisateurs/livreur_dashboard.html', {
        'commandes': page_obj,
        'en_attente': en_attente,
        'en_preparation': en_preparation,
        'en_livraison': en_livraison,
        'livrees': livrees,
    })


@livreur_required
def livreur_commandes(request):
    statut = request.GET.get('statut', '')
    page = request.GET.get('page', 1)
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
    })


STATUTS_TRANSITIONS_LIVREUR = {
    'en_attente': ['en_preparation'],
    'en_preparation': ['en_livraison'],
    'en_livraison': ['livree', 'livraison_echouee'],
    'livree': [],
    'livraison_echouee': [],
}


@livreur_required
def livreur_update_status(request, commande_id):
    commande = get_object_or_404(Commande, id=commande_id, livreur=request.user)
    if request.method == 'POST':
        nouveau_statut = request.POST.get('statut')
        transitions_valides = STATUTS_TRANSITIONS_LIVREUR.get(commande.statut, [])
        if nouveau_statut in transitions_valides:
            commande.statut = nouveau_statut
            commande.save()
            messages.success(request, f'Statut mis à jour : {commande.get_statut_display()}.')

            if nouveau_statut == 'livree':
                _envoyer_email_livraison(commande)
        else:
            messages.error(request, 'Transition de statut invalide.')
        return redirect('livreur_commandes')
    return redirect('livreur_commandes')

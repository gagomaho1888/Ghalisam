from datetime import datetime, timedelta
from decimal import Decimal

from django.contrib.auth.models import User
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.core.paginator import Paginator
from django.db.models import Count, Min, Sum
from django.db.models.functions import TruncDay, TruncMonth
from django.utils import timezone
from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer
from .models import Commande, Livreur, Notification
from .decorators import admin_required
from .whatsapp import notifier_livreur_whatsapp


@admin_required
def admin_dashboard(request):
    commandes = Commande.objects.all().select_related('user', 'livreur')
    total_commandes = commandes.count()
    commandes_en_attente = commandes.filter(statut=Commande.StatutChoices.EN_ATTENTE).count()
    commandes_livrees = commandes.filter(statut=Commande.StatutChoices.LIVREE).count()
    commandes_encours = commandes.filter(
        statut=Commande.StatutChoices.EN_ATTENTE, livreur__isnull=False
    ).count()
    livreurs_actifs = Livreur.objects.filter(est_actif=True).count()
    commandes_sans_livreur = commandes.filter(livreur__isnull=True).count()
    recentes = commandes[:5]
    return render(request, 'Utilisateurs/admin_dashboard.html', {
        'total_commandes': total_commandes,
        'commandes_en_attente': commandes_en_attente,
        'commandes_livrees': commandes_livrees,
        'commandes_encours': commandes_encours,
        'livreurs_actifs': livreurs_actifs,
        'commandes_sans_livreur': commandes_sans_livreur,
        'commandes': recentes,
    })


@admin_required
def gestion_livreurs(request):
    livreurs = Livreur.objects.all().select_related('user').order_by('-date_creation')
    return render(request, 'Utilisateurs/gestion_livreurs.html', {
        'livreurs': livreurs,
    })


@admin_required
def create_livreur(request):
    if request.method == 'POST':
        username = request.POST.get('username', '').strip()
        password = request.POST.get('password', '')
        telephone = request.POST.get('telephone', '').strip()
        if not username or not password:
            messages.error(request, 'Nom d\'utilisateur et mot de passe requis.')
        elif User.objects.filter(username=username).exists():
            messages.error(request, 'Ce nom d\'utilisateur existe déjà.')
        else:
            user = User.objects.create_user(username=username, password=password)
            Livreur.objects.create(user=user, telephone=telephone)
            messages.success(request, f'Livreur "{username}" créé avec succès.')
            return redirect('gestion_livreurs')
    return render(request, 'Utilisateurs/create_livreur.html')


@admin_required
def edit_livreur(request, livreur_id):
    livreur = get_object_or_404(Livreur.objects.select_related('user'), id=livreur_id)
    if request.method == 'POST':
        username = request.POST.get('username', '').strip()
        password = request.POST.get('password', '').strip()
        telephone = request.POST.get('telephone', '').strip()
        if not username:
            messages.error(request, 'Le nom d\'utilisateur est requis.')
        else:
            if User.objects.filter(username=username).exclude(id=livreur.user.id).exists():
                messages.error(request, 'Ce nom d\'utilisateur est déjà pris.')
            else:
                livreur.user.username = username
                if password:
                    livreur.user.set_password(password)
                livreur.user.save()
                livreur.telephone = telephone
                livreur.save()
                messages.success(request, 'Livreur mis à jour.')
                return redirect('gestion_livreurs')
    return render(request, 'Utilisateurs/edit_livreur.html', {'livreur': livreur})


@admin_required
def toggle_livreur(request, livreur_id):
    if request.method != 'POST':
        return redirect('gestion_livreurs')
    livreur = get_object_or_404(Livreur, id=livreur_id)
    livreur.est_actif = not livreur.est_actif
    livreur.save()
    status = 'activé' if livreur.est_actif else 'désactivé'
    messages.success(request, f'Livreur "{livreur.user.username}" {status}.')
    return redirect('gestion_livreurs')


@admin_required
def delete_livreur(request, livreur_id):
    if request.method != 'POST':
        return redirect('gestion_livreurs')
    livreur = get_object_or_404(Livreur, id=livreur_id)
    username = livreur.user.username
    Commande.objects.filter(livreur=livreur.user).update(livreur=None)
    livreur.delete()
    messages.success(request, f'Livreur "{username}" supprimé.')
    return redirect('gestion_livreurs')


@admin_required
def toutes_commandes(request):
    statut = request.GET.get('statut', '')
    page = request.GET.get('page', 1)
    commandes = Commande.objects.all().select_related('user', 'livreur').order_by('-created_at')
    if statut:
        commandes = commandes.filter(statut=statut)
    paginator = Paginator(commandes, 20)
    page_obj = paginator.get_page(page)
    livreurs = Livreur.objects.filter(est_actif=True).select_related('user')
    return render(request, 'Utilisateurs/toutes_commandes.html', {
        'commandes': page_obj,
        'livreurs': livreurs,
        'statut_selectionne': statut,
    })


@admin_required
def attribuer_commande(request, commande_id):
    commande = get_object_or_404(Commande, id=commande_id)
    if request.method == 'POST':
        livreur_id = request.POST.get('livreur_id')
        ancien_livreur = commande.livreur
        if livreur_id:
            livreur = get_object_or_404(Livreur, id=livreur_id, est_actif=True)
            if not livreur.est_disponible and livreur.user != ancien_livreur:
                messages.error(
                    request,
                    f'Le livreur {livreur.user.username} est indisponible : '
                    'aucune nouvelle commande ne peut lui être attribuée.'
                )
                return redirect('attribuer_commande', commande_id=commande.id)

            reattribution = commande.statut == Commande.StatutChoices.LIVRAISON_ECHOUEE
            commande.livreur = livreur.user
            if reattribution:
                commande.statut = Commande.StatutChoices.EN_ATTENTE
            commande.save()

            if ancien_livreur != livreur.user:
                Notification.objects.create(
                    livreur=livreur.user,
                    commande=commande,
                    message=(
                        f'Commande {commande.ticket} réattribuée après un échec de livraison.'
                        if reattribution
                        else f'Nouvelle commande {commande.ticket} assignée.'
                    )
                )

                channel_layer = get_channel_layer()
                async_to_sync(channel_layer.group_send)(
                    f'livreur_{livreur.user.id}',
                    {
                        'type': 'nouvelle_commande',
                        'ticket': commande.ticket,
                        'client': commande.fullname or commande.user.username,
                        'telephone': commande.telephone,
                        'adresse': commande.adresse or (f"{commande.ville}, {commande.pays}" if commande.ville else "—"),
                        'montant': str(commande.total_price),
                        'commande_id': commande.id,
                        'message': f'Nouvelle commande {commande.ticket} attribuée !',
                        'livreur_name': livreur.user.get_full_name() or livreur.user.username,
                    }
                )

                notifier_livreur_whatsapp(livreur.telephone, commande)

            livreur.marquer_indisponible_si_occupe()

            ancien_profil = getattr(ancien_livreur, 'livreur_profile', None)
            if ancien_profil and ancien_profil != livreur:
                ancien_profil.marquer_disponible_si_libre()

            if reattribution:
                messages.success(
                    request,
                    f'Commande {commande.ticket} réattribuée à {livreur.user.username} '
                    'et remise en attente.'
                )
            else:
                messages.success(
                    request,
                    f'Commande {commande.ticket} attribuée à {livreur.user.username}.'
                )
        else:
            profil = getattr(ancien_livreur, 'livreur_profile', None)
            commande.livreur = None
            commande.save()
            if profil:
                profil.marquer_disponible_si_libre()
            messages.success(request, f'Attribution retirée pour {commande.ticket}.')
        return redirect('toutes_commandes')
    livreurs = Livreur.objects.filter(est_actif=True).select_related('user')
    return render(request, 'Utilisateurs/attribuer_commande.html', {
        'commande': commande,
        'livreurs': livreurs,
    })


# ---------------------------------------------------------------------------
# Suivi des ventes
# ---------------------------------------------------------------------------

PERIODE_SUIVI_DEFAUT = '30j'

PERIODES_SUIVI = {
    '7j': {'label': '7 derniers jours', 'jours': 7, 'granularite': 'jour'},
    '30j': {'label': '30 derniers jours', 'jours': 30, 'granularite': 'jour'},
    '90j': {'label': '90 derniers jours', 'jours': 90, 'granularite': 'jour'},
    '12m': {'label': '12 derniers mois', 'jours': 365, 'granularite': 'mois'},
    'tout': {'label': 'Depuis le début', 'jours': None, 'granularite': 'mois'},
}

MOIS_COURTS = {
    1: 'janv.', 2: 'févr.', 3: 'mars', 4: 'avr.', 5: 'mai', 6: 'juin',
    7: 'juil.', 8: 'août', 9: 'sept.', 10: 'oct.', 11: 'nov.', 12: 'déc.',
}


def _ventes_encaissees(debut=None, fin=None):
    """Commandes de la période, hors livraisons échouées (pas de CA encaissé)."""
    qs = Commande.objects.exclude(statut=Commande.StatutChoices.LIVRAISON_ECHOUEE)
    if debut is not None:
        qs = qs.filter(created_at__gte=debut)
    if fin is not None:
        qs = qs.filter(created_at__lt=fin)
    return qs


def _toutes_commandes(debut=None, fin=None):
    qs = Commande.objects.all()
    if debut is not None:
        qs = qs.filter(created_at__gte=debut)
    if fin is not None:
        qs = qs.filter(created_at__lt=fin)
    return qs


def _stats_ventes(debut=None, fin=None):
    ventes = _ventes_encaissees(debut, fin)
    totaux = ventes.aggregate(ca=Sum('total_price'), frais=Sum('shipping_cost'))
    ca = totaux['ca'] or Decimal('0')
    frais = totaux['frais'] or Decimal('0')
    nb_ventes = ventes.count()
    toutes = _toutes_commandes(debut, fin)
    return {
        'ca': ca,
        'ca_articles': ca - frais,
        'frais_livraison': frais,
        'nb_commandes': toutes.count(),
        'nb_ventes': nb_ventes,
        'nb_livrees': ventes.filter(statut=Commande.StatutChoices.LIVREE).count(),
        'nb_echouees': toutes.filter(statut=Commande.StatutChoices.LIVRAISON_ECHOUEE).count(),
        'nb_clients': ventes.values('user_id').distinct().count(),
        'panier_moyen': (ca / nb_ventes) if nb_ventes else Decimal('0'),
    }


def _evolution(actuel, precedent):
    """Variation en % entre deux valeurs, None si la base est nulle."""
    if precedent in (0, Decimal('0')) or precedent is None:
        return None
    return ((Decimal(actuel) - Decimal(precedent)) / Decimal(precedent)) * 100


def _plages_periodes(debut, granularite, aujourdhui):
    """Liste continue des périodes (jour ou mois) entre debut et aujourd'hui."""
    if granularite == 'jour':
        plages = []
        jour = debut.date()
        while jour <= aujourdhui.date():
            plages.append(jour)
            jour += timedelta(days=1)
        return plages

    plages = []
    annee, mois = debut.year, debut.month
    while (annee, mois) <= (aujourdhui.year, aujourdhui.month):
        premier = datetime(annee, mois, 1, tzinfo=timezone.get_current_timezone())
        if mois == 12:
            suivant = datetime(annee + 1, 1, 1, tzinfo=timezone.get_current_timezone())
        else:
            suivant = datetime(annee, mois + 1, 1, tzinfo=timezone.get_current_timezone())
        plages.append(premier)
        annee, mois = suivant.year, suivant.month
    return plages


def _serie_ventes(debut, granularite, aujourdhui):
    """Série CA / commandes par jour ou par mois, sans trou."""
    trunc = TruncDay('created_at') if granularite == 'jour' else TruncMonth('created_at')
    lignes = (
        _ventes_encaissees(debut)
        .annotate(cle=trunc)
        .values('cle')
        .annotate(ca=Sum('total_price'), nb_commandes=Count('id'))
    )

    par_mois = granularite == 'mois'
    index = {}
    for ligne in lignes:
        cle = ligne['cle']
        index[(cle.year, cle.month) if par_mois else cle.date()] = {
            'ca': ligne['ca'] or Decimal('0'),
            'nb_commandes': ligne['nb_commandes'] or 0,
        }

    series = []
    for plage in _plages_periodes(debut, granularite, aujourdhui):
        if par_mois:
            label = f'{plage.month:02d}/{plage.year}'
            label_long = f'{MOIS_COURTS[plage.month]} {plage.year}'
        else:
            label = plage.strftime('%d/%m')
            label_long = f'{plage.day} {MOIS_COURTS[plage.month]} {plage.year}'
        donnees = index.get(
            (plage.year, plage.month) if par_mois else plage,
            {'ca': Decimal('0'), 'nb_commandes': 0},
        )
        series.append({
            'label': label,
            'label_long': label_long,
            'ca': donnees['ca'],
            'nb_commandes': donnees['nb_commandes'],
        })

    max_ca = max((s['ca'] for s in series), default=Decimal('0'))
    max_cmd = max((s['nb_commandes'] for s in series), default=0)
    for s in series:
        s['hauteur_ca'] = round(float(s['ca'] / max_ca) * 100, 2) if max_ca else 0
        s['hauteur_cmd'] = round((s['nb_commandes'] / max_cmd) * 100, 2) if max_cmd else 0
    return series


def _borne_debut(periode, premiere_commande):
    """Date de début de la période demandée."""
    if periode['jours']:
        return timezone.now() - timedelta(days=periode['jours'])
    if premiere_commande is not None:
        return premiere_commande
    return timezone.now() - timedelta(days=365)


@admin_required
def suivi_ventes(request):
    code_periode = request.GET.get('periode', PERIODE_SUIVI_DEFAUT)
    if code_periode not in PERIODES_SUIVI:
        code_periode = PERIODE_SUIVI_DEFAUT
    periode = PERIODES_SUIVI[code_periode]

    granularite = request.GET.get('granularite') or periode['granularite']
    if granularite not in ('jour', 'mois'):
        granularite = periode['granularite']

    aujourdhui = timezone.localtime()
    premiere = Commande.objects.aggregate(Min('created_at'))['created_at__min']
    debut = timezone.localtime(_borne_debut(periode, premiere))

    if periode['jours']:
        debut_precedent = debut - timedelta(days=periode['jours'])
    elif premiere is not None:
        debut_precedent = timezone.localtime(premiere)
    else:
        debut_precedent = debut

    stats = _stats_ventes(debut, None)
    stats_precedentes = _stats_ventes(debut_precedent, debut)
    series = _serie_ventes(debut, granularite, aujourdhui)

    for point in series:
        point['panier_moyen'] = (
            point['ca'] / point['nb_commandes'] if point['nb_commandes'] else Decimal('0')
        )
        point['part_ca'] = round(float(point['ca'] / stats['ca']) * 100, 1) if stats['ca'] else 0

    evolutions = {
        cle: _evolution(stats[cle], stats_precedentes[cle])
        for cle in ('ca', 'nb_commandes', 'panier_moyen', 'ca_articles')
    }

    return render(request, 'Utilisateurs/suivi_ventes.html', {
        'stats': stats,
        'stats_precedentes': stats_precedentes,
        'evolutions': evolutions,
        'series': series,
        'granularite': granularite,
        'periode': periode,
        'periode_code': code_periode,
        'periodes': PERIODES_SUIVI,
        'debut': debut,
    })

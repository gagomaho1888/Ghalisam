from django.contrib.auth.models import User
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.core.paginator import Paginator
from django.db.models import Q
from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer
from .models import Commande, Livreur, Notification
from .decorators import admin_required
from .whatsapp import notifier_livreur_whatsapp


@admin_required
def admin_dashboard(request):
    commandes = Commande.objects.all().select_related('user', 'livreur')
    total_commandes = commandes.count()
    commandes_en_attente = commandes.filter(statut='en_attente').count()
    commandes_livrees = commandes.filter(statut='livree').count()
    commandes_encours = commandes.filter(
        Q(statut='en_preparation') | Q(statut='en_livraison')
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
            commande.livreur = livreur.user
            commande.save()

            if ancien_livreur != livreur.user:
                Notification.objects.create(
                    livreur=livreur.user,
                    commande=commande,
                    message=f'Nouvelle commande {commande.ticket} assignée.'
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

            messages.success(
                request,
                f'Commande {commande.ticket} attribuée à {livreur.user.username}.'
            )
        else:
            commande.livreur = None
            commande.save()
            messages.success(request, f'Attribution retirée pour {commande.ticket}.')
        return redirect('toutes_commandes')
    livreurs = Livreur.objects.filter(est_actif=True).select_related('user')
    return render(request, 'Utilisateurs/attribuer_commande.html', {
        'commande': commande,
        'livreurs': livreurs,
    })

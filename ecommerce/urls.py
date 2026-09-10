import os
from django.contrib import admin
from django.urls import path, include
from Utilisateurs import views as user_views
from Utilisateurs import admin_views
from Utilisateurs import livreur_views
from Utilisateurs import api_views
from Articles import boutique_views
from django.conf import settings
from django.conf.urls.static import static
from . import error_views
from dbfiles import views as dbfiles_views

handler404 = 'ecommerce.error_views.page_404'
handler500 = 'ecommerce.error_views.page_500'

urlpatterns = [
    path('admin/', admin.site.urls),
    path('', include('Articles.urls')),

    path('connexion/', user_views.connexion, name='connexion'),
    path('register/', user_views.inscription, name='register'),
    path('verifier-email/', user_views.verifier_email, name='verifier_email'),
    path('renvoyer-code/', user_views.resend_code, name='resend_code'),
    path('mot-de-passe-oublie/', user_views.mot_de_passe_oublie, name='mot_de_passe_oublie'),
    path('reinitialiser-mot-de-passe/', user_views.reinitialiser_mdp, name='reinitialiser_mdp'),
    path('profil/', user_views.profil, name='profil'),
    path('deconnexion/', user_views.deconnexion, name='deconnexion'),

    path('admin-dashboard/', admin_views.admin_dashboard, name='admin_dashboard'),
    path('admin-dashboard/livreurs/', admin_views.gestion_livreurs, name='gestion_livreurs'),
    path('admin-dashboard/livreurs/creer/', admin_views.create_livreur, name='create_livreur'),
    path('admin-dashboard/livreurs/<int:livreur_id>/modifier/', admin_views.edit_livreur, name='edit_livreur'),
    path('admin-dashboard/livreurs/<int:livreur_id>/activer-desactiver/', admin_views.toggle_livreur, name='toggle_livreur'),
    path('admin-dashboard/livreurs/<int:livreur_id>/supprimer/', admin_views.delete_livreur, name='delete_livreur'),
    path('admin-dashboard/commandes/', admin_views.toutes_commandes, name='toutes_commandes'),
    path('admin-dashboard/commandes/<int:commande_id>/attribuer/', admin_views.attribuer_commande, name='attribuer_commande'),

    path('admin-dashboard/boutique/', boutique_views.gestion_boutique, name='gestion_boutique'),
    path('admin-dashboard/boutique/ajouter/', boutique_views.ajouter_article, name='ajouter_article'),
    path('admin-dashboard/boutique/<int:article_id>/modifier/', boutique_views.modifier_article, name='modifier_article'),
    path('admin-dashboard/boutique/<int:article_id>/supprimer/', boutique_views.supprimer_article, name='supprimer_article'),
    path('admin-dashboard/boutique/<int:article_id>/disponible/', boutique_views.basculer_disponible, name='basculer_disponible'),

    path('livreur/', livreur_views.livreur_dashboard, name='livreur_dashboard'),
    path('livreur/commandes/', livreur_views.livreur_commandes, name='livreur_commandes'),
    path('livreur/commandes/<int:commande_id>/statut/', livreur_views.livreur_update_status, name='livreur_update_status'),

    path('api/notifications/', api_views.api_notifications, name='api_notifications'),
    path('api/notifications/lues/', api_views.api_notifications_lues, name='api_notifications_lues'),
    path('api/notifications/non-lues/', api_views.api_notifications_non_lues_count, name='api_notifications_non_lues_count'),

    path('db-files/<path:path>', dbfiles_views.serve_file, name='db_file'),
]

# Media files : servi par Django en dev, par nginx en prod.
# Passer DJANGO_SERVE_MEDIA=True pour forcer Django à servir les media même en prod
_serve_media = settings.DEBUG or os.environ.get('DJANGO_SERVE_MEDIA', 'False').strip().lower() in ('1', 'true', 'yes', 'on')
if _serve_media:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)

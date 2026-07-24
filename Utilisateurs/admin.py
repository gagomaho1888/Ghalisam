from django.contrib import admin
from .models import Utilisateur, Commande, Livreur


@admin.register(Livreur)
class LivreurAdmin(admin.ModelAdmin):
    list_display = ('user', 'telephone', 'est_actif', 'date_creation')
    search_fields = ('user__username', 'telephone')
    list_filter = ('est_actif',)


@admin.register(Utilisateur)
class UtilisateurAdmin(admin.ModelAdmin):
    list_display = ('nom', 'prenom', 'adresse', 'ville', 'pays', 'code_postal', 'telephone')
    search_fields = ('nom__username', 'prenom', 'adresse')


@admin.register(Commande)
class CommandeAdmin(admin.ModelAdmin):
    list_display = ('ticket', 'user', 'statut', 'livreur', 'ville', 'pays', 'total_price', 'created_at')
    list_editable = ('statut',)
    search_fields = ('ticket', 'user__username', 'livreur__username', 'ville', 'pays', 'telephone')
    list_filter = ('statut', 'pays', 'created_at')

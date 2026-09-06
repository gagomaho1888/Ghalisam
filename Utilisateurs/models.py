from django.db import models
from django.contrib.auth.models import User


class Livreur(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='livreur_profile')
    telephone = models.CharField(max_length=20, blank=True)
    est_actif = models.BooleanField(default=True)
    date_creation = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Livreur {self.user.username}"


class Notification(models.Model):
    livreur = models.ForeignKey(User, on_delete=models.CASCADE, related_name='notifications')
    commande = models.ForeignKey('Commande', on_delete=models.CASCADE, null=True, blank=True)
    message = models.CharField(max_length=255)
    lue = models.BooleanField(default=False)
    date_creation = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-date_creation']
        indexes = [
            models.Index(fields=['livreur', 'lue']),
        ]

    def __str__(self):
        return f"Notification pour {self.livreur.username}: {self.message[:50]}"


class Utilisateur(models.Model):
    nom = models.OneToOneField(User, on_delete=models.CASCADE)
    prenom = models.CharField(max_length=100, blank=True)
    adresse = models.CharField(max_length=255, blank=True)
    telephone = models.CharField(max_length=20, blank=True)
    ville = models.CharField(max_length=100, blank=True)
    pays = models.CharField(max_length=100, blank=True)
    code_postal = models.CharField(max_length=20, blank=True)
    code_validation = models.CharField(max_length=64, blank=True, default='', help_text='Hash SHA-256 (HMAC) du code de validation.')
    email_verified = models.BooleanField(default=False)
    code_validation_expires = models.DateTimeField(null=True, blank=True)

    def __str__(self):
        return self.nom.username


class Commande(models.Model):
    class StatutChoices(models.TextChoices):
        EN_ATTENTE = 'en_attente', 'En attente'
        EN_PREPARATION = 'en_preparation', 'En préparation'
        EN_LIVRAISON = 'en_livraison', 'En livraison'
        LIVREE = 'livree', 'Livrée'
        LIVRAISON_ECHOUEE = 'livraison_echouee', 'Livraison échouée'

    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='commandes')
    ticket = models.CharField(max_length=50, unique=True)
    statut = models.CharField(max_length=20, choices=StatutChoices.choices, default=StatutChoices.EN_ATTENTE, db_index=True)
    livreur = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='commandes_livreur')
    fullname = models.CharField(max_length=200, blank=True)
    adresse = models.CharField(max_length=255, blank=True)
    ville = models.CharField(max_length=100, blank=True)
    pays = models.CharField(max_length=100, blank=True)
    code_postal = models.CharField(max_length=20, blank=True)
    telephone = models.CharField(max_length=20, blank=True)
    total_price = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    shipping_cost = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    items = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['user', 'statut']),
            models.Index(fields=['livreur', 'statut']),
        ]

    def __str__(self):
        return f"Commande {self.ticket} - {self.user.username}"

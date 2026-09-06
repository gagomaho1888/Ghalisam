from django.db import models
from django.db.models import Sum
from django.contrib.auth.models import User


def _stock_label(stock):
    if stock <= 0:
        return 'Épuisé'
    if stock <= 5:
        return 'Bientôt épuisé'
    return 'En stock'


class Article(models.Model):
    class CategorieChoices(models.TextChoices):
        HAUT = 'haut', 'Vêtement Haut'
        BAS = 'bas', 'Vêtement Bas'
        CHAUSSURE = 'chaussure', 'Chaussure'

    class TailleChoices(models.TextChoices):
        S = 'S', 'S'
        M = 'M', 'M'
        L = 'L', 'L'
        XL = 'XL', 'XL'
        XXL = 'XXL', 'XXL'
        SIZE_35 = '35', '35'
        SIZE_36 = '36', '36'
        SIZE_37 = '37', '37'
        SIZE_38 = '38', '38'
        SIZE_39 = '39', '39'
        SIZE_40 = '40', '40'
        SIZE_41 = '41', '41'
        SIZE_42 = '42', '42'
        SIZE_43 = '43', '43'
        SIZE_44 = '44', '44'
        SIZE_45 = '45', '45'
        SIZE_46 = '46', '46'

    nom = models.CharField(max_length=200)
    slug = models.SlugField(unique=True)
    description = models.TextField()
    prix = models.DecimalField(max_digits=10, decimal_places=2)
    stock = models.PositiveIntegerField(default=0)
    image = models.ImageField(upload_to='articles/', blank=True, null=True)
    disponible = models.BooleanField(default=True)
    marque = models.CharField(max_length=100, blank=True)
    categorie = models.CharField(
        max_length=20,
        choices=CategorieChoices.choices,
        default=CategorieChoices.HAUT,
    )
    taille = models.CharField(
        max_length=4,
        choices=TailleChoices.choices,
        blank=True,
        default='',
    )
    poids = models.DecimalField(
        max_digits=6,
        decimal_places=2,
        blank=True,
        null=True,
    )
    couleur = models.CharField(max_length=50, blank=True, default='')
    date_creation = models.DateTimeField(auto_now_add=True)
    date_modification = models.DateTimeField(auto_now=True)

    @property
    def total_stock(self):
        result = self.variantes.aggregate(total=Sum('stock'))['total']
        return result if result is not None else self.stock

    @property
    def stock_status(self):
        return _stock_label(self.total_stock)

    @property
    def is_out_of_stock(self):
        return self.total_stock <= 0

    def __str__(self):
        return f"{self.nom} ({self.get_categorie_display()} - {self.taille})"


class ArticleVariant(models.Model):
    article = models.ForeignKey(Article, related_name='variantes', on_delete=models.CASCADE)
    taille = models.CharField(max_length=4, choices=Article.TailleChoices.choices)
    couleur = models.CharField(max_length=50, blank=True, default='')
    stock = models.PositiveIntegerField(default=0)

    class Meta:
        unique_together = ('article', 'taille', 'couleur')
        verbose_name = 'Variation de taille'
        verbose_name_plural = 'Variations de taille'

    @property
    def stock_status(self):
        return _stock_label(self.stock)

    def __str__(self):
        suffix = f" - {self.couleur}" if self.couleur else ''
        return f"{self.article.nom} - {self.get_taille_display()}{suffix} ({self.stock})"


class NewsletterSubscriber(models.Model):
    email = models.EmailField(unique=True)
    date_inscription = models.DateTimeField(auto_now_add=True)
    actif = models.BooleanField(default=True)

    def __str__(self):
        return self.email


class Review(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='reviews')
    article = models.ForeignKey(Article, on_delete=models.CASCADE, related_name='reviews')
    rating = models.PositiveSmallIntegerField(choices=[(1, '1'), (2, '2'), (3, '3'), (4, '4'), (5, '5')])
    comment = models.TextField()
    image = models.ImageField(upload_to='reviews/', blank=True, null=True)
    seller_response = models.TextField(blank=True)
    achat_verifie = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ('user', 'article')
        ordering = ['-created_at']
        verbose_name = 'Avis'
        verbose_name_plural = 'Avis'

    def __str__(self):
        return f"Avis de {self.user.username} sur {self.article.nom}"

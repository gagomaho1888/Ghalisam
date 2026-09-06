from django import forms
from django.core.exceptions import ValidationError
from django.utils.text import slugify
from PIL import Image as PillowImage
from .models import Review, Article, ArticleVariant

ALLOWED_EXTENSIONS = {'.jpg', '.jpeg', '.png', '.webp', '.gif'}
MAX_IMAGE_SIZE = 5 * 1024 * 1024


def _valider_contenu_image(image, field_name):
    ext = image.name[image.name.rfind('.'):].lower()
    if ext not in ALLOWED_EXTENSIONS:
        raise ValidationError('Format non autorisé. Utilisez JPG, PNG, WebP ou GIF.')
    if image.size > MAX_IMAGE_SIZE:
        raise ValidationError('L\'image ne doit pas dépasser 5 Mo.')
    # Vérifie le contenu réel (magic bytes) et non seulement l'extension.
    try:
        image.seek(0)
        with PillowImage.open(image) as img:
            img.verify()
    except Exception:
        raise ValidationError('Fichier image invalide ou corrompu.')
    image.seek(0)
    return image


class ArticleVariantForm(forms.ModelForm):
    class Meta:
        model = ArticleVariant
        fields = ['taille', 'couleur', 'stock']
        labels = {
            'taille': 'Taille',
            'couleur': 'Couleur',
            'stock': 'Stock',
        }


class ArticleAdminForm(forms.ModelForm):
    class Meta:
        model = Article
        fields = [
            'nom', 'slug', 'categorie', 'description', 'prix', 'stock',
            'couleur', 'marque', 'poids', 'taille', 'image', 'disponible',
        ]
        widgets = {
            'description': forms.Textarea(attrs={'rows': 4}),
        }
        labels = {
            'nom': 'Nom de l\'article',
            'disponible': 'Disponible à la vente',
        }

    def clean_slug(self):
        slug = self.cleaned_data.get('slug')
        if not slug:
            slug = slugify(self.cleaned_data.get('nom', ''))
        queryset = Article.objects.filter(slug=slug)
        if self.instance.pk:
            queryset = queryset.exclude(pk=self.instance.pk)
        if queryset.exists():
            raise forms.ValidationError('Ce slug est déjà utilisé.')
        return slug

    def clean_image(self):
        image = self.cleaned_data.get('image')
        if not image:
            return image
        return _valider_contenu_image(image, 'image')


class ReviewForm(forms.ModelForm):
    class Meta:
        model = Review
        fields = ['rating', 'comment', 'image']
        widgets = {
            'rating': forms.HiddenInput(),
            'comment': forms.Textarea(attrs={
                'placeholder': 'Partagez votre expérience avec cet article...',
                'rows': 4,
                'class': 'review-textarea',
            }),
            'image': forms.FileInput(attrs={
                'class': 'review-image-input',
                'accept': 'image/*',
            }),
        }
        labels = {
            'rating': 'Note',
            'comment': 'Votre avis',
            'image': 'Ajouter une photo (facultatif)',
        }

    def clean_rating(self):
        rating = self.cleaned_data.get('rating')
        if rating is None or rating < 1 or rating > 5:
            raise forms.ValidationError('Veuillez sélectionner une note entre 1 et 5.')
        return rating

    def clean_comment(self):
        comment = self.cleaned_data.get('comment', '').strip()
        if not comment:
            raise forms.ValidationError('Veuillez écrire un commentaire.')
        if len(comment) < 10:
            raise forms.ValidationError('Le commentaire doit contenir au moins 10 caractères.')
        if len(comment) > 5000:
            raise forms.ValidationError('Le commentaire ne peut pas dépasser 5000 caractères.')
        return comment

    def clean_image(self):
        image = self.cleaned_data.get('image')
        if not image:
            return image
        return _valider_contenu_image(image, 'image')

from django import forms
from django.core.exceptions import ValidationError
from .models import Review

ALLOWED_EXTENSIONS = {'.jpg', '.jpeg', '.png', '.webp', '.gif'}
MAX_IMAGE_SIZE = 5 * 1024 * 1024


class ReviewForm(forms.ModelForm):
    class Meta:
        model = Review
        fields = ['rating', 'comment', 'image']
        widgets = {
            'rating': forms.HiddenInput(),
            'comment': forms.Textarea(attrs={
                'placeholder': 'Partagez votre expérience avec ce produit...',
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
        ext = image.name[image.name.rfind('.'):].lower()
        if ext not in ALLOWED_EXTENSIONS:
            raise ValidationError('Format non autorisé. Utilisez JPG, PNG, WebP ou GIF.')
        if image.size > MAX_IMAGE_SIZE:
            raise ValidationError('L\'image ne doit pas dépasser 5 Mo.')
        return image

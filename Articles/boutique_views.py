from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.core.paginator import Paginator
from django.core.files.storage import default_storage
from django.db import transaction
from Utilisateurs.decorators import admin_required
from .models import Article, ArticleVariant
from .forms import ArticleAdminForm, ArticleVariantForm


@admin_required
def gestion_boutique(request):
    query = request.GET.get('q', '').strip()
    categorie = request.GET.get('categorie', '').strip()
    articles_qs = Article.objects.prefetch_related('variantes').order_by('-date_creation')
    if query:
        articles_qs = articles_qs.filter(nom__icontains=query)
    if categorie:
        articles_qs = articles_qs.filter(categorie=categorie)
    paginator = Paginator(articles_qs, 15)
    page_obj = paginator.get_page(request.GET.get('page', 1))
    return render(request, 'Articles/admin/gestion_boutique.html', {
        'articles': page_obj,
        'query': query,
        'categorie': categorie,
    })


@admin_required
def ajouter_article(request):
    if request.method == 'POST':
        form = ArticleAdminForm(request.POST, request.FILES)
        if form.is_valid():
            article = form.save()
            _sauvegarder_variantes(request, article)
            messages.success(request, f'Article "{article.nom}" ajouté avec succès.')
            return redirect('gestion_boutique')
    else:
        form = ArticleAdminForm()
    return render(request, 'Articles/admin/article_form.html', {
        'form': form,
        'titre': 'Ajouter un article',
        'variantes': [ArticleVariantForm()],
        'article': None,
    })


@admin_required
def modifier_article(request, article_id):
    article = get_object_or_404(Article.objects.prefetch_related('variantes'), id=article_id)
    if request.method == 'POST':
        form = ArticleAdminForm(request.POST, request.FILES, instance=article)
        if form.is_valid():
            article = form.save()
            _sauvegarder_variantes(request, article)
            messages.success(request, f'Article "{article.nom}" modifié avec succès.')
            return redirect('gestion_boutique')
    else:
        form = ArticleAdminForm(instance=article)
    variantes = [ArticleVariantForm(instance=v) for v in article.variantes.all()]
    return render(request, 'Articles/admin/article_form.html', {
        'form': form,
        'titre': f'Modifier : {article.nom}',
        'variantes': variantes,
        'article': article,
    })


def _sauvegarder_variantes(request, article):
    tailles = request.POST.getlist('variant_taille')
    couleurs = request.POST.getlist('variant_couleur')
    stocks = request.POST.getlist('variant_stock')
    ids = request.POST.getlist('variant_id')

    existing_ids = []
    for i, taille in enumerate(tailles):
        taille = taille.strip()
        if not taille:
            continue
        stock_val = 0
        try:
            stock_val = int(stocks[i]) if i < len(stocks) else 0
        except (ValueError, TypeError):
            stock_val = 0
        couleur = couleurs[i].strip() if i < len(couleurs) else ''
        vid = ids[i].strip() if i < len(ids) else ''

        if vid and vid.isdigit():
            variant = ArticleVariant.objects.filter(id=int(vid), article=article).first()
            if variant:
                variant.taille = taille
                variant.couleur = couleur
                variant.stock = stock_val
                variant.save()
                existing_ids.append(variant.id)
        else:
            variant = ArticleVariant(article=article, taille=taille, couleur=couleur, stock=stock_val)
            variant.save()
            existing_ids.append(variant.id)

    article.variantes.exclude(id__in=existing_ids).delete()


@admin_required
def supprimer_article(request, article_id):
    article = get_object_or_404(Article, id=article_id)
    if request.method == 'POST':
        nom = article.nom
        if article.image:
            image_path = article.image.name
            try:
                default_storage.delete(image_path)
            except Exception:
                pass
        article.delete()
        messages.success(request, f'Article "{nom}" supprimé.')
    return redirect('gestion_boutique')


@admin_required
def basculer_disponible(request, article_id):
    article = get_object_or_404(Article, id=article_id)
    if request.method == 'POST':
        article.disponible = not article.disponible
        article.save()
        etat = 'disponible' if article.disponible else 'masqué'
        messages.success(request, f'Article "{article.nom}" est maintenant {etat}.')
    return redirect('gestion_boutique')
from django.contrib import admin
from .models import Article, ArticleVariant, NewsletterSubscriber, Review


class ArticleVariantInline(admin.TabularInline):
    model = ArticleVariant
    extra = 1
    min_num = 1
    verbose_name = 'Variation de taille'
    verbose_name_plural = 'Variations de taille'


@admin.register(Article)
class ArticleAdmin(admin.ModelAdmin):
    inlines = [ArticleVariantInline]
    list_display = ('nom', 'prix', 'stock', 'display_total_stock', 'stock_status', 'disponible')
    list_filter = ('disponible', 'categorie')
    search_fields = ('nom', 'description')
    prepopulated_fields = {'slug': ('nom',)}

    def display_total_stock(self, obj):
        return obj.total_stock
    display_total_stock.short_description = 'Stock total'


@admin.register(NewsletterSubscriber)
class NewsletterSubscriberAdmin(admin.ModelAdmin):
    list_display = ('email', 'date_inscription', 'actif')
    list_filter = ('actif', 'date_inscription')
    search_fields = ('email',)
    date_hierarchy = 'date_inscription'
    actions = ['desactiver_subscribers', 'activer_subscribers']

    def desactiver_subscribers(self, request, queryset):
        queryset.update(actif=False)
    desactiver_subscribers.short_description = 'Désactiver les abonnés sélectionnés'

    def activer_subscribers(self, request, queryset):
        queryset.update(actif=True)
    activer_subscribers.short_description = 'Activer les abonnés sélectionnés'


@admin.register(Review)
class ReviewAdmin(admin.ModelAdmin):
    list_display = ('user', 'article', 'rating', 'achat_verifie', 'created_at', 'has_seller_response')
    list_filter = ('rating', 'achat_verifie', 'article', 'user')
    search_fields = ('comment', 'user__username', 'article__nom')
    list_select_related = ('user', 'article')
    date_hierarchy = 'created_at'
    readonly_fields = ('created_at', 'updated_at')
    fieldsets = (
        (None, {
            'fields': ('user', 'article', 'rating', 'comment', 'image', 'achat_verifie')
        }),
        ('Réponse du vendeur', {
            'fields': ('seller_response',),
            'classes': ('wide',),
        }),
        ('Métadonnées', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',),
        }),
    )

    def has_seller_response(self, obj):
        return bool(obj.seller_response)
    has_seller_response.short_description = 'Réponse'
    has_seller_response.boolean = True
from django.urls import path
from . import views

urlpatterns = [
    path('', views.acceuil, name='acceuil'),
    path('produits/', views.produit_list, name='produit_list'),
    path('produit/<int:article_id>/', views.produit_detail, name='produit_detail'),
    path('panier/', views.commande, name='commande'),
    path('panier/ajouter/', views.add_to_cart, name='add_to_cart'),
    path('panier/update/', views.update_cart, name='update_cart'),
    path('panier/remove/', views.remove_from_cart, name='remove_from_cart'),
    path('newsletter/', views.newsletter_subscribe, name='newsletter_subscribe'),
    path('produit/<int:article_id>/avis/ajouter/', views.add_review, name='add_review'),
    path('avis/<int:review_id>/modifier/', views.edit_review, name='edit_review'),
    path('avis/<int:review_id>/supprimer/', views.delete_review, name='delete_review'),
    path('api/produit/<int:article_id>/avis/', views.get_reviews, name='get_reviews'),
    path('api/geocode/search/', views.geocode_search, name='geocode_search'),
    path('api/geocode/reverse/', views.geocode_reverse, name='geocode_reverse'),
    path('faq/', views.faq, name='faq'),
    path('contact/', views.contact, name='contact'),
    path('livraison-retours/', views.livraison_retours, name='livraison_retours'),
    path('cgu/', views.cgu, name='cgu'),
    path('cgv/', views.cgv, name='cgv'),
    path('cookies/', views.cookies, name='cookies'),
    path('mentions-legales/', views.mentions_legales, name='mentions_legales'),
    path('politique-confidentialite/', views.politique_confidentialite, name='politique_confidentialite'),
    path('cookie-consent/', views.cookie_consent, name='cookie_consent'),
]

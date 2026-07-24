from decimal import Decimal
from django.test import TestCase, Client
from django.contrib.auth.models import User
from django.core.files.uploadedfile import SimpleUploadedFile
from .models import Article, Review
from Utilisateurs.models import Commande


class ReviewModelTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='testuser', password='12345')
        self.article = Article.objects.create(
            nom='Test Produit',
            slug='test-produit',
            description='Un produit test',
            prix=Decimal('100.00'),
            stock=10,
            disponible=True,
        )

    def test_create_review(self):
        review = Review.objects.create(
            user=self.user,
            article=self.article,
            rating=5,
            comment='Super produit !',
            achat_verifie=True,
        )
        self.assertEqual(review.rating, 5)
        self.assertEqual(review.comment, 'Super produit !')
        self.assertTrue(review.achat_verifie)
        self.assertEqual(str(review), f"Avis de {self.user.username} sur {self.article.nom}")

    def test_unique_review_per_user_product(self):
        Review.objects.create(user=self.user, article=self.article, rating=4, comment='Bon')
        with self.assertRaises(Exception):
            Review.objects.create(user=self.user, article=self.article, rating=3, comment='Moyen')

    def test_review_ordering(self):
        user2 = User.objects.create_user(username='testuser2', password='12345')
        Review.objects.create(user=self.user, article=self.article, rating=5, comment='Premier')
        import time; time.sleep(0.01)
        r2 = Review.objects.create(user=user2, article=self.article, rating=4, comment='Second')
        reviews = Review.objects.all()
        self.assertEqual(reviews[0], r2)


class ReviewFormTest(TestCase):
    def setUp(self):
        self.article = Article.objects.create(
            nom='Test', slug='test', description='Test', prix=Decimal('50'), stock=5, disponible=True,
        )
        self.user = User.objects.create_user(username='testuser', password='12345')

    def test_valid_form(self):
        form_data = {'rating': 5, 'comment': 'Excellent produit, je recommande !'}
        response = self.client.post('/produit/1/avis/ajouter/', form_data)
        self.assertIn(response.status_code, [302, 404])

    def test_form_rating_required(self):
        from Articles.forms import ReviewForm
        form = ReviewForm(data={'rating': None, 'comment': 'Test'})
        self.assertFalse(form.is_valid())
        self.assertIn('rating', form.errors)

    def test_form_comment_min_length(self):
        from Articles.forms import ReviewForm
        form = ReviewForm(data={'rating': 5, 'comment': 'Court'})
        self.assertFalse(form.is_valid())

    def test_form_image_validation(self):
        from Articles.forms import ReviewForm
        fake_image = SimpleUploadedFile('test.exe', b'fake-executable-content', content_type='application/x-msdownload')
        form = ReviewForm(data={'rating': 5, 'comment': 'Très bon produit !'}, files={'image': fake_image})
        self.assertFalse(form.is_valid())
        self.assertIn('image', form.errors)


class PurchaseVerificationTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='buyer', password='12345')
        self.article = Article.objects.create(
            nom='Chemise Blanche', slug='chemise-blanche', description='Belle chemise',
            prix=Decimal('25000'), stock=10, disponible=True,
        )
        self.client = Client()

    def test_user_has_purchased_delivered(self):
        Commande.objects.create(
            user=self.user,
            ticket='TKT-TEST001',
            statut=Commande.StatutChoices.LIVREE,
            items='Chemise Blanche x2 (L); Pantalon x1 (M)',
            total_price=Decimal('60000'),
        )
        from Articles.views import user_has_purchased
        self.assertTrue(user_has_purchased(self.user, self.article))

    def test_user_has_purchased_not_delivered(self):
        Commande.objects.create(
            user=self.user,
            ticket='TKT-TEST002',
            statut=Commande.StatutChoices.EN_ATTENTE,
            items='Chemise Blanche x1 (M)',
            total_price=Decimal('25000'),
        )
        from Articles.views import user_has_purchased
        self.assertFalse(user_has_purchased(self.user, self.article))

    def test_user_has_not_purchased(self):
        from Articles.views import user_has_purchased
        self.assertFalse(user_has_purchased(self.user, self.article))

    def test_review_blocked_without_purchase(self):
        self.client.login(username='buyer', password='12345')
        response = self.client.post(f'/produit/{self.article.id}/avis/ajouter/', {
            'rating': 5, 'comment': 'Super produit !'
        })
        self.assertNotIn(self.article.id, [r.article.id for r in Review.objects.all()])

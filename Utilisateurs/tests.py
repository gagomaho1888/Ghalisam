from django.test import TestCase, Client, override_settings
from django.urls import reverse
from django.contrib.auth.models import User
from .models import Livreur, Commande, Notification, Utilisateur


class NotificationModelTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='livreur1', password='test123')
        self.livreur = Livreur.objects.create(user=self.user)
        self.client_user = User.objects.create_user(username='client1', password='test123')
        self.commande = Commande.objects.create(
            user=self.client_user,
            ticket='TKT-TEST',
            total_price=15000,
            ville='Abidjan',
            pays='Côte d\'Ivoire',
        )

    def test_creation_notification(self):
        n = Notification.objects.create(
            livreur=self.user,
            commande=self.commande,
            message=f'Nouvelle commande {self.commande.ticket} assignée.'
        )
        self.assertEqual(Notification.objects.count(), 1)
        self.assertEqual(n.livreur, self.user)
        self.assertEqual(n.commande, self.commande)
        self.assertFalse(n.lue)

    def test_notification_lue(self):
        n = Notification.objects.create(livreur=self.user, commande=self.commande, message='Test')
        n.lue = True
        n.save()
        self.assertTrue(Notification.objects.get(id=n.id).lue)

    def test_notifications_non_lues(self):
        Notification.objects.create(livreur=self.user, message='Notif 1')
        Notification.objects.create(livreur=self.user, message='Notif 2', lue=True)
        Notification.objects.create(livreur=self.user, message='Notif 3')
        self.assertEqual(Notification.objects.filter(livreur=self.user, lue=False).count(), 2)


class NotificationAPITest(TestCase):
    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user(username='livreur2', password='test123')
        self.livreur = Livreur.objects.create(user=self.user)
        for i in range(3):
            Notification.objects.create(livreur=self.user, message=f'Notif {i+1}')

    def test_api_notifications_non_authentifie(self):
        response = self.client.get(reverse('api_notifications'))
        self.assertEqual(response.status_code, 302)

    def test_api_notifications_livreur(self):
        self.client.login(username='livreur2', password='test123')
        response = self.client.get(reverse('api_notifications'))
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data['non_lues'], 3)
        self.assertEqual(len(data['notifications']), 3)

    def test_api_notifications_non_lues_count(self):
        self.client.login(username='livreur2', password='test123')
        response = self.client.get(reverse('api_notifications_non_lues_count'))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['non_lues'], 3)

    def test_api_marquer_lues(self):
        self.client.login(username='livreur2', password='test123')
        response = self.client.post(reverse('api_notifications_lues'))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(Notification.objects.filter(livreur=self.user, lue=False).count(), 0)

    def test_api_non_livreur_bloque(self):
        user = User.objects.create_user(username='normal', password='test123')
        self.client.login(username='normal', password='test123')
        response = self.client.get(reverse('api_notifications'))
        self.assertEqual(response.status_code, 302)


class LivreurDashboardAccessTest(TestCase):
    def setUp(self):
        self.client = Client()
        self.admin = User.objects.create_superuser(username='admin', password='test123')
        self.livreur_user = User.objects.create_user(username='livreur3', password='test123')
        self.livreur = Livreur.objects.create(user=self.livreur_user)

    def test_livreur_dashboard_acces_livreur(self):
        self.client.login(username='livreur3', password='test123')
        response = self.client.get(reverse('livreur_dashboard'))
        self.assertEqual(response.status_code, 200)

    def test_livreur_dashboard_bloque_admin(self):
        self.client.login(username='admin', password='test123')
        response = self.client.get(reverse('livreur_dashboard'))
        self.assertEqual(response.status_code, 302)

    def test_livreur_dashboard_bloque_non_connecte(self):
        response = self.client.get(reverse('livreur_dashboard'))
        self.assertEqual(response.status_code, 302)


@override_settings(CHANNEL_LAYERS={
    'default': {'BACKEND': 'channels.layers.InMemoryChannelLayer'},
})
class CommandeLivreeurAttributionTest(TestCase):
    def setUp(self):
        self.client = Client()
        self.admin = User.objects.create_superuser(username='admin', password='test123')
        self.client_user = User.objects.create_user(username='client2', password='test123')
        self.livreur_user = User.objects.create_user(username='livreur4', password='test123')
        self.livreur = Livreur.objects.create(user=self.livreur_user)
        self.commande = Commande.objects.create(
            user=self.client_user,
            ticket='TKT-ATTR',
            total_price=25000,
        )

    def test_attribution_cree_notification(self):
        self.client.login(username='admin', password='test123')
        self.client.post(reverse('attribuer_commande', args=[self.commande.id]), {
            'livreur_id': self.livreur.id
        })
        self.assertTrue(
            Notification.objects.filter(
                livreur=self.livreur_user, commande=self.commande
            ).exists()
        )

    def test_livreur_voit_ses_commandes(self):
        self.commande.livreur = self.livreur_user
        self.commande.save()
        autre = Commande.objects.create(user=self.client_user, ticket='TKT-AUTRE')
        self.client.login(username='livreur4', password='test123')
        response = self.client.get(reverse('livreur_dashboard'))
        commandes = response.context['commandes']
        self.assertEqual(len(list(commandes)), 1)
        self.assertEqual(list(commandes)[0], self.commande)

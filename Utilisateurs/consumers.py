import json
from channels.generic.websocket import AsyncWebsocketConsumer
from django.contrib.auth.models import User


def _origin_autorise(scope):
    """Vérifie l'en-tête Origin pour empêcher le Cross-Site WebSocket Hijacking."""
    from django.conf import settings
    origin = None
    for name, value in scope.get('headers', []):
        if name == b'origin':
            origin = value.decode('latin-1')
            break
    if not origin:
        return False
    host = origin.split('://', 1)[-1].split('/', 1)[0]
    if settings.DEBUG:
        autorises = {'localhost', '127.0.0.1'}
        if host.split(':')[0] in autorises:
            return True
    return host in settings.ALLOWED_HOSTS


class NotificationConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        if not _origin_autorise(self.scope):
            await self.close(code=4403)
            return
        self.user = self.scope['user']
        if self.user.is_anonymous or not hasattr(self.user, 'livreur_profile') or not self.user.livreur_profile.est_actif:
            await self.close()
            return
        self.group_name = f'livreur_{self.user.id}'
        await self.channel_layer.group_add(self.group_name, self.channel_name)
        await self.accept()

    async def disconnect(self, close_code):
        if hasattr(self, 'group_name'):
            await self.channel_layer.group_discard(self.group_name, self.channel_name)

    async def receive(self, text_data):
        pass

    async def nouvelle_commande(self, event):
        await self.send(text_data=json.dumps({
            'type': 'nouvelle_commande',
            'ticket': event['ticket'],
            'client': event['client'],
            'telephone': event['telephone'],
            'adresse': event['adresse'],
            'montant': event['montant'],
            'commande_id': event['commande_id'],
            'message': event['message'],
            'livreur_name': event.get('livreur_name', ''),
        }))


class AdminNotificationConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        if not _origin_autorise(self.scope):
            await self.close(code=4403)
            return
        self.user = self.scope['user']
        if self.user.is_anonymous or not self.user.is_staff:
            await self.close()
            return
        self.group_name = 'admin_notifications'
        await self.channel_layer.group_add(self.group_name, self.channel_name)
        await self.accept()

    async def disconnect(self, close_code):
        if hasattr(self, 'group_name'):
            await self.channel_layer.group_discard(self.group_name, self.channel_name)

    async def receive(self, text_data):
        pass

    async def nouvelle_commande_admin(self, event):
        await self.send(text_data=json.dumps({
            'type': 'nouvelle_commande',
            'ticket': event['ticket'],
            'client': event['client'],
            'telephone': event['telephone'],
            'adresse': event['adresse'],
            'ville': event.get('ville', ''),
            'pays': event.get('pays', ''),
            'montant': event['montant'],
            'articles': event['articles'],
            'commande_id': event['commande_id'],
        }))

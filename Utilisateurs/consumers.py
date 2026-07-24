import json
from channels.generic.websocket import AsyncWebsocketConsumer


class NotificationConsumer(AsyncWebsocketConsumer):
    async def connect(self):
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

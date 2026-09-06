from django.urls import re_path
from Utilisateurs import consumers

websocket_urlpatterns = [
    re_path(r'ws/notifications/$', consumers.NotificationConsumer.as_asgi()),
    re_path(r'ws/admin/notifications/$', consumers.AdminNotificationConsumer.as_asgi()),
]

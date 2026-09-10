import mimetypes

from django.core.files.base import ContentFile
from django.core.files.storage import Storage

from .models import StoredFile


class DatabaseFileStorage(Storage):
    """Stocke les fichiers (images) dans PostgreSQL au lieu du disque.

    Utilisé pour Render/Neon car le disque de Render est éphémère
    (effacé à chaque déploiement).
    """

    def _save(self, name, content):
        content.seek(0)
        data = content.read()
        StoredFile.objects.update_or_create(
            path=name,
            defaults={'content': data, 'size': len(data)},
        )
        return name

    def _open(self, name, mode='rb'):
        try:
            obj = StoredFile.objects.get(path=name)
        except StoredFile.DoesNotExist:
            raise FileNotFoundError(name)
        return ContentFile(obj.content, name=name)

    def exists(self, name):
        return StoredFile.objects.filter(path=name).exists()

    def delete(self, name):
        StoredFile.objects.filter(path=name).delete()

    def size(self, name):
        return StoredFile.objects.get(path=name).size

    def url(self, name):
        return f'/db-files/{name}'
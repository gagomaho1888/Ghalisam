from django.db import models


class StoredFile(models.Model):
    path = models.TextField(unique=True)
    content = models.BinaryField()
    size = models.PositiveBigIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Fichier stocké'
        verbose_name_plural = 'Fichiers stockés'

    def __str__(self):
        return self.path
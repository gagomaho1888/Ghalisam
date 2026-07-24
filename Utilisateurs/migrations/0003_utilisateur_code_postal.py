from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('Utilisateurs', '0002_commande'),
    ]

    operations = [
        migrations.AddField(
            model_name='utilisateur',
            name='code_postal',
            field=models.CharField(blank=True, max_length=20, default=''),
            preserve_default=False,
        ),
    ]

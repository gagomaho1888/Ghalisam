from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('Utilisateurs', '0001_initial'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='Commande',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('ticket', models.CharField(max_length=50)),
                ('fullname', models.CharField(blank=True, max_length=200)),
                ('adresse', models.CharField(blank=True, max_length=255)),
                ('ville', models.CharField(blank=True, max_length=100)),
                ('pays', models.CharField(blank=True, max_length=100)),
                ('code_postal', models.CharField(blank=True, max_length=20)),
                ('telephone', models.CharField(blank=True, max_length=20)),
                ('total_price', models.DecimalField(decimal_places=2, default=0, max_digits=10)),
                ('items', models.TextField(blank=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('user', models.ForeignKey(on_delete=models.deletion.CASCADE, related_name='commandes', to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'ordering': ['-created_at'],
            },
        ),
    ]

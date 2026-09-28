from django.db import migrations, models

STATUTS_RETIRES = ['en_preparation', 'en_livraison']


def ramener_en_attente(apps, schema_editor):
    Commande = apps.get_model('Utilisateurs', 'Commande')
    Commande.objects.filter(statut__in=STATUTS_RETIRES).update(statut='en_attente')


def laisser_en_place(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ('Utilisateurs', '0019_livreur_est_disponible'),
    ]

    operations = [
        migrations.RunPython(ramener_en_attente, laisser_en_place),
        migrations.AlterField(
            model_name='commande',
            name='statut',
            field=models.CharField(choices=[('en_attente', 'En attente'), ('livree', 'Livrée'), ('livraison_echouee', 'Livraison échouée')], db_index=True, default='en_attente', max_length=20),
        ),
    ]

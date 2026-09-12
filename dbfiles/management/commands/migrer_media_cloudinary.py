import mimetypes
import os

import cloudinary.api
import cloudinary.exceptions
import cloudinary.uploader
from django.conf import settings
from django.core.files.base import ContentFile
from django.core.files.storage import FileSystemStorage, default_storage
from django.core.management.base import BaseCommand

from Articles.models import Article, Review
from dbfiles.models import StoredFile
from dbfiles.storage import DatabaseFileStorage


def get_media_tag():
    try:
        from cloudinary_storage import app_settings
        return app_settings.MEDIA_TAG
    except Exception:
        return 'media'


class Command(BaseCommand):
    help = (
        "Migre les fichiers enregistrés (disque local ou base Neon via "
        "dbfiles.storage.DatabaseFileStorage) vers Cloudinary, puis met à jour "
        "les champs image des modèles. À exécuter une fois le backend Cloudinary "
        "activé, sur Render (ou en local avec les identifiants Cloudinary)."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            '--purge',
            action='store_true',
            help='Supprime les lignes StoredFile (base Neon) après upload réussi.',
        )
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Affiche les fichiers à migrer sans rien envoyer.',
        )

    def handle(self, *args, **options):
        dry_run = options['dry_run']
        purge = options['purge']

        backend = str(getattr(default_storage, '__class__', type(default_storage)))
        if 'MediaCloudinaryStorage' not in backend and 'CloudinaryStorage' not in backend:
            self.stderr.write(self.style.ERROR(
                'Le stockage par défaut n\'est pas Cloudinary. '
                'Vérifiez que CLOUDINARY_CLOUD_NAME/API_KEY/API_SECRET (ou CLOUDINARY_URL) '
                'sont définis. Backend actuel : %s' % backend
            ))
            return

        self.stdout.write('Lecture des anciens fichiers (base Neon / disque local)...')

        reader_db = DatabaseFileStorage()
        reader_fs = FileSystemStorage(location=str(settings.MEDIA_ROOT))

        # 1) Collecte des chemins à migrer : toutes les lignes StoredFile
        #    (y compris les fichiers "orphelins" comme l'image du bandeau)
        #    + les images référencées par les modèles.
        paths = set(StoredFile.objects.values_list('path', flat=True))
        for obj in Article.objects.exclude(image='').iterator():
            if obj.image.name:
                paths.add(obj.image.name)
        for obj in Review.objects.exclude(image='').iterator():
            if obj.image.name:
                paths.add(obj.image.name)

        if not paths:
            self.stdout.write(self.style.SUCCESS('Rien à migrer : aucun fichier trouvé.'))
            return

        self.stdout.write('%d fichiers à (re)vérifier.' % len(paths))

        mapping = {}
        uploaded = 0
        skipped = 0
        not_found = 0

        for path in sorted(paths):
            public_id = self._cloudinary_public_id(path)

            if self._exists_in_cloudinary(public_id):
                skipped += 1
                mapping[path] = public_id
                continue

            data = self._read_bytes(path, reader_db, reader_fs)
            if data is None:
                not_found += 1
                self.stderr.write(self.style.WARNING(
                    'Introuvable (ni en base ni sur disque) : %s' % path
                ))
                continue

            if dry_run:
                mapping[path] = public_id
                uploaded += 1
                continue

            resource_type = 'image' if self._looks_like_image(path) else 'raw'
            try:
                cloudinary.uploader.upload(
                    ContentFile(data),
                    public_id=public_id,
                    resource_type=resource_type,
                    overwrite=True,
                    tags=[self._media_tag()],
                )
            except Exception as exc:
                self.stderr.write(self.style.ERROR(
                    'Échec upload %s -> %s : %s' % (path, public_id, exc)
                ))
                continue

            mapping[path] = public_id
            uploaded += 1

        if dry_run:
            self.stdout.write(self.style.WARNING(
                'DRY-RUN : %d upload(s) simulé(s), %d déjà présent(s), %d introuvable(s).'
                % (uploaded, skipped, not_found)
            ))
            for path, public_id in mapping.items():
                self.stdout.write('  %s -> %s' % (path, public_id))
            return

        # 2) Mise à jour des champs ImageField pour pointer vers les public_id.
        self._update_field(Article, 'image', mapping)
        self._update_field(Review, 'image', mapping)

        # 3) Purge optionnelle de la base Neon.
        if purge:
            purged = StoredFile.objects.filter(path__in=list(mapping)).delete()
            self.stdout.write(self.style.SUCCESS(
                'StoredFile purgés (base Neon) : %s' % (purged[0],)
            ))

        self.stdout.write(self.style.SUCCESS(
            'Migration terminée : %d uploade(s), %d déjà présent(s), %d introuvable(s).'
            % (uploaded, skipped, not_found)
        ))
        if not purge:
            self.stdout.write(self.style.WARNING(
                'Astuce : relancez avec --purge une fois vos fichiers vérifiés '
                'pour libérer le stockage Neon (importante économie de crédits).'
            ))

    # ------------------------------------------------------------------

    def _cloudinary_public_id(self, path):
        folder = os.path.dirname(path)
        base = os.path.splitext(os.path.basename(path))[0]
        return '%s/%s' % (folder, base) if folder else base

    def _exists_in_cloudinary(self, public_id):
        try:
            cloudinary.api.resource(public_id)
            return True
        except cloudinary.exceptions.NotFound:
            return False
        except Exception:
            return False

    def _read_bytes(self, path, reader_db, reader_fs):
        for reader in (reader_db, reader_fs):
            try:
                if reader.exists(path):
                    with reader.open(path) as fh:
                        return fh.read()
            except Exception:
                continue
        return None

    def _looks_like_image(self, path):
        content_type = mimetypes.guess_type(path)[0] or ''
        return content_type.startswith('image/')

    def _media_tag(self):
        return get_media_tag()

    def _update_field(self, model, field_name, mapping):
        changed = 0
        qs = model.objects.exclude(**{'%s__isnull' % field_name: True})
        qs = qs.exclude(**{field_name: ''})
        for obj in qs.iterator():
            name = getattr(obj, field_name).name
            new_name = mapping.get(name)
            if new_name and new_name != name:
                getattr(obj, field_name).name = new_name
                obj.save(update_fields=[field_name])
                changed += 1
        if changed:
            self.stdout.write('%s : %d champ(s) mis à jour.' % (model.__name__, changed))
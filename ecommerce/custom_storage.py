"""Stockage Cloudinary avec URLs sans version.

Le backend cloudinary_storage génère par défaut des URLs du type
.../image/upload/v1/<public_id>. C'est le journal de cache : après un 404
mis en cache (période où les fichiers n'étaient pas encore uploadés), les
URLs /v1/ renvoient des 404 fantômes selon la zone géographique. En
désactivant force_version, l'URL devient .../image/upload/<public_id>,
consolidée par le CDN et vérifiée (GET/HEAD 200).
"""

import cloudinary
from cloudinary_storage.storage import MediaCloudinaryStorage


class VersionlessMediaCloudinaryStorage(MediaCloudinaryStorage):
    """MediaCloudinaryStorage sans version dans l'URL."""

    def _get_url(self, name):
        name = self._normalise_name(name)
        name = self._prepend_prefix(name)
        resource = cloudinary.CloudinaryResource(
            name,
            default_resource_type=self._get_resource_type(name),
            url_options={'force_version': False},
        )
        return resource.url
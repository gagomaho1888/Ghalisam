import mimetypes

from django.http import Http404, HttpResponse

from .models import StoredFile


def serve_file(request, path):
    try:
        obj = StoredFile.objects.get(path=path)
    except StoredFile.DoesNotExist:
        raise Http404('Fichier introuvable')
    content_type = mimetypes.guess_type(path)[0] or 'application/octet-stream'
    response = HttpResponse(obj.content, content_type=content_type)
    response['Content-Length'] = obj.size
    response['Cache-Control'] = 'public, max-age=31536000, immutable'
    return response
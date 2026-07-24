from django.http import JsonResponse
from django.contrib.auth.decorators import login_required
from .models import Notification
from .decorators import livreur_required


@login_required
@livreur_required
def api_notifications(request):
    notifications = Notification.objects.filter(
        livreur=request.user, lue=False
    ).select_related('commande').order_by('-date_creation')[:20]
    data = [{
        'id': n.id,
        'message': n.message,
        'commande_id': n.commande.id if n.commande else None,
        'ticket': n.commande.ticket if n.commande else '',
        'date': n.date_creation.isoformat(),
    } for n in notifications]
    return JsonResponse({'notifications': data, 'non_lues': len(data)})


@login_required
@livreur_required
def api_notifications_lues(request):
    if request.method == 'POST':
        Notification.objects.filter(livreur=request.user, lue=False).update(lue=True)
        return JsonResponse({'ok': True})
    return JsonResponse({'error': 'POST required'}, status=405)


@login_required
@livreur_required
def api_notifications_non_lues_count(request):
    count = Notification.objects.filter(livreur=request.user, lue=False).count()
    return JsonResponse({'non_lues': count})

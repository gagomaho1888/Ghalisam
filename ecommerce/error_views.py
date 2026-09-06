from django.shortcuts import render


def page_404(request, exception=None):
    return render(request, '404.html', status=404)


def page_500(request):
    return render(request, '500.html', status=500)
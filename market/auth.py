from functools import wraps

from django.http import JsonResponse

from .models import ApiToken


def api_auth(view):
    @wraps(view)
    def wrapped(request, *args, **kwargs):
        header = request.headers.get('Authorization', '')
        if not header.startswith('Token '):
            return JsonResponse({'error': 'Authentication required.'}, status=401)
        try:
            request.user = ApiToken.objects.select_related('user').get(key=header[6:]).user
        except ApiToken.DoesNotExist:
            return JsonResponse({'error': 'Invalid token.'}, status=401)
        if not request.user.is_active:
            return JsonResponse({'error': 'This account is blocked.'}, status=403)
        return view(request, *args, **kwargs)
    return wrapped

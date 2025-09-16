from django.views.decorators.csrf import ensure_csrf_cookie
from django.http import JsonResponse
from django.contrib.auth.decorators import login_required

@login_required
@ensure_csrf_cookie
def get_socket_token(request):
    # For development only, create or retrieve a token associated with the user
    token = "user-specific-development-token"
    return JsonResponse({"token": token})

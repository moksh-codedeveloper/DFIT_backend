from django.urls import path
from .views import get_socket_token

urlpatterns = [
    path("socket-token/", get_socket_token, name="get_socket_token")
]
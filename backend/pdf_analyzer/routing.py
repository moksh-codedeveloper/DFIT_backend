from consumers import FileUploadConsumer
from django.urls import re_path


websocket_urlpatterns = [
    re_path(r'^ws/files/$', FileUploadConsumer.as_asgi())
]
from django.urls import path
from .views import analyze_and_cleanup_pdfs

urlpatterns = [
    path('fetch/<str:user_id>/', analyze_and_cleanup_pdfs, name="pdf-fetch")
]

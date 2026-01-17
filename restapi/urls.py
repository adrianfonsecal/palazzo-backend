# proyecto_palazzo/urls.py (Archivo principal)
from django.contrib import admin
from django.urls import path, include
from core.webhooks import whatsapp_webhook    # <--- 1. IMPORTA TU NUEVA FUNCIÓN AQUÍ
from core.views import PublicLeadCreateView    # <--- 1. IMPORTA TU NUEVA FUNCIÓN AQUÍ
from rest_framework_simplejwt.views import (
    TokenObtainPairView,
    TokenRefreshView,
)
urlpatterns = [
    path('admin/', admin.site.urls),
    path('api/token/', TokenObtainPairView.as_view(), name='token_obtain_pair'),
    path('api/token/refresh/', TokenRefreshView.as_view(), name='token_refresh'),
    path('webhooks/whatsapp/', whatsapp_webhook, name='whatsapp_webhook'),
    path('api/public/contact/', PublicLeadCreateView.as_view(), name='public-lead-create'),
    path('', include('core.urls')),
]
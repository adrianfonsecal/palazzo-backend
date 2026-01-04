from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from rest_framework.routers import DefaultRouter

# Importamos las vistas que definimos en el paso anterior
from .views import (
    WeddingPublicViewSet,
    InvitationPublicViewSet,
    PhotoUploadViewSet,
    InvitationAdminViewSet,
    GuestAdminViewSet
)


# -----------------------------------------------------------------------------
# CONFIGURACIÓN DEL ROUTER
# -----------------------------------------------------------------------------
router = DefaultRouter()

# 1. Rutas Públicas (Para Invitados)
# -----------------------------------------------------
# URL: /api/wedding/{slug}/
# Ejemplo: /api/wedding/juan-y-maria/
router.register(r'api/wedding', WeddingPublicViewSet, basename='wedding-public')

# URL: /api/invitation/{uuid}/
# Ejemplo: /api/invitation/a8098c1a-28bc-4372.../
# Nota: DRF detecta automáticamente el lookup_field='uuid' que definimos en la View
router.register(r'api/invitation', InvitationPublicViewSet, basename='invitation-public')

# URL: /api/photos/
# Permite subir (POST) y listar (GET) fotos
router.register(r'api/photos', PhotoUploadViewSet, basename='photos-upload')


# 2. Rutas Privadas (CRM / Admin de Novios)
# -----------------------------------------------------
# URL: /api/admin/invitations/
# Incluye las acciones extra: /api/admin/invitations/import_csv/
router.register(r'api/admin/invitations', InvitationAdminViewSet, basename='admin-invitations')

# URL: /api/admin/guests/

router.register(r'api/admin/guests', GuestAdminViewSet, basename='admin-guests')


# -----------------------------------------------------------------------------
# URL PATTERNS PRINCIPALES
# -----------------------------------------------------------------------------
urlpatterns = router.urls

# -----------------------------------------------------------------------------
# SOLO PARA DESARROLLO (Serving Media Files)
# -----------------------------------------------------------------------------
# Esto permite que Django sirva las imágenes subidas cuando estás probando en local.
# En producción (AWS S3), esto no se usa porque las URLs vendrán directas de S3.
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
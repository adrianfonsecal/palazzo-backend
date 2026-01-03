from rest_framework import viewsets, mixins, status, permissions
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.parsers import MultiPartParser, FormParser
from django.shortcuts import get_object_or_404
import os
from django.core.files.storage import default_storage
from .tasks import import_guests_task # Importamos la tarea
from .models import Wedding, Invitation, Photo
from .serializers import (
    WeddingPublicSerializer, 
    InvitationPublicSerializer, 
    InvitationAdminSerializer,
    PhotoSerializer
)

# -----------------------------------------------------------------------------
# 1. VISTA PÚBLICA DE LA BODA (Solo Lectura)
# -----------------------------------------------------------------------------
class WeddingPublicViewSet(viewsets.GenericViewSet, mixins.RetrieveModelMixin):
    """
    Permite al frontend obtener la configuración visual de la boda (colores, mapa, nombres)
    usando el 'slug' (ej: /api/wedding/juan-y-maria/).
    """
    queryset = Wedding.objects.all()
    serializer_class = WeddingPublicSerializer
    permission_classes = [permissions.AllowAny]
    lookup_field = 'slug'


# -----------------------------------------------------------------------------
# 2. VISTA PÚBLICA DE INVITACIÓN (El corazón del sistema para invitados)
# -----------------------------------------------------------------------------
class InvitationPublicViewSet(viewsets.GenericViewSet, 
                              mixins.RetrieveModelMixin, 
                              mixins.UpdateModelMixin):
    """
    Maneja la interacción del invitado con su invitación.
    - GET: Ve sus datos y los de su familia.
    - PATCH: Confirma asistencia (RSVP).
    
    SEGURIDAD: No usa auth de usuario, usa el UUID como token de acceso.
    """
    queryset = Invitation.objects.all()
    serializer_class = InvitationPublicSerializer
    permission_classes = [permissions.AllowAny]
    lookup_field = 'uuid' # La URL será /api/invitation/{uuid}/

    def update(self, request, *args, **kwargs):
        """
        Sobreescribimos update para asegurar que solo se puedan hacer cambios parciales (PATCH).
        """
        kwargs['partial'] = True
        return super().update(request, *args, **kwargs)


# -----------------------------------------------------------------------------
# 3. VISTA PARA SUBIR FOTOS (Álbum Colaborativo)
# -----------------------------------------------------------------------------
class PhotoUploadViewSet(viewsets.GenericViewSet, mixins.CreateModelMixin, mixins.ListModelMixin):
    """
    Permite subir fotos vinculándolas a una invitación específica.
    """
    queryset = Photo.objects.filter(is_approved=True) # Solo mostramos las aprobadas
    serializer_class = PhotoSerializer
    permission_classes = [permissions.AllowAny]
    parser_classes = (MultiPartParser, FormParser) # Necesario para subir archivos

    def get_queryset(self):
        """
        Filtrar fotos por boda (usando un query param ?wedding_slug=juan-y-maria)
        """
        slug = self.request.query_params.get('wedding_slug')
        if slug:
            return self.queryset.filter(wedding__slug=slug)
        return Photo.objects.none() # No mostramos nada si no especifican la boda

    def perform_create(self, serializer):
        """
        Aquí vinculamos la foto con la invitación que la subió.
        El Frontend debe enviar el 'invitation_uuid' junto con la foto.
        """
        # 1. Obtenemos el UUID de la invitación desde los datos del form
        invitation_uuid = self.request.data.get('invitation_uuid')
        
        # 2. Validamos que la invitación exista
        invitation = get_object_or_404(Invitation, uuid=invitation_uuid)
        
        # 3. Guardamos la foto vinculándola a la Boda y a la Invitación
        serializer.save(
            wedding=invitation.wedding,
            uploaded_by=invitation
        )


# -----------------------------------------------------------------------------
# 4. VISTA ADMIN / CRM (Para los Novios)
# -----------------------------------------------------------------------------
class InvitationAdminViewSet(viewsets.ModelViewSet):
    """
    CRUD completo para el panel de administración de los novios.
    Requiere Login.
    """
    serializer_class = InvitationAdminSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        """
        MULTI-TENANCY:
        Aseguramos que el usuario solo vea las invitaciones DE SU PROPIA BODA.
        Asumimos que el modelo User tiene relación con Wedding o se gestiona el perfil.
        """
        # Ejemplo simplificado: El usuario es 'owner' de la boda
        # return Invitation.objects.filter(wedding__owner_user=self.request.user)
        
        # Por ahora devolvemos todo (ajustar según tu modelo de User)
        return Invitation.objects.all()

    @action(detail=False, methods=['post'])
    def import_csv(self, request):
        """
        Endpoint especial para recibir el CSV y procesarlo en segundo plano (Celery).
        """
        file = request.FILES.get('file')
        wedding_id = request.data.get('wedding_id')
        
        if not file:
            return Response({"error": "No file provided"}, status=status.HTTP_400_BAD_REQUEST)

        # Aquí llamarías a tu tarea de Celery
        # process_csv_import.delay(wedding_id, file.read().decode('utf-8'))
        
        return Response({"status": "Importación iniciada. Te avisaremos cuando termine."}, status=status.HTTP_202_ACCEPTED)
    
    @action(detail=False, methods=['post'])
    def send_whatsapp_blast(self, request):
        """
        Recibe una lista de IDs de invitaciones para enviar.
        Payload esperado: { "invitation_ids": ["uuid-1", "uuid-2", ...] }
        """
        # 1. Obtener la lista de IDs que enviaron los novios
        invitation_ids = request.data.get('invitation_ids', [])
        
        if not invitation_ids:
            return Response(
                {"error": "Debes seleccionar al menos una invitación."}, 
                status=status.HTTP_400_BAD_REQUEST
            )

        # 2. Validar que esos IDs pertenezcan realmente a esta boda (Seguridad)
        # Asumiendo que ya tienes filtrado el queryset por usuario/boda:
        # valid_ids = self.get_queryset().filter(uuid__in=invitation_ids).values_list('uuid', flat=True)
        # Convertimos a lista de strings para pasarlo a Celery (que requiere datos serializables JSON)
        
        # Por simplicidad del ejemplo, pasamos la lista directa, 
        # pero la tarea debe re-validar.
        
        # 3. Llamar a la tarea con la lista específica
        from core.tasks import send_whatsapp_list_task
        send_whatsapp_list_task.delay(invitation_ids)
        
        return Response(
            {"status": f"Se han encolado {len(invitation_ids)} invitaciones para envío."}, 
            status=status.HTTP_202_ACCEPTED
        )
    
    @action(detail=False, methods=['post'])
    def import_csv(self, request):
        file = request.FILES.get('file')
        wedding_id = request.data.get('wedding_id') # O sacarlo del usuario logueado
        
        if not file:
            return Response({"error": "No file"}, status=400)

        # 1. Guardamos el archivo temporalmente en disco/S3 para que Celery pueda leerlo
        # (Celery no puede recibir el archivo 'en memoria' eficientemente)
        file_name = f"imports/wedding_{wedding_id}_{file.name}"
        file_path = default_storage.save(file_name, file)
        
        # Obtenemos la ruta absoluta del sistema
        full_path = default_storage.path(file_path)

        # 2. Llamamos a la tarea asíncrona
        # .delay() es lo que manda la tarea a Redis
        import_guests_task.delay(wedding_id, full_path)
        
        return Response({"status": "Procesando archivo..."}, status=202)
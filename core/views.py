from rest_framework import viewsets, mixins, status, permissions, serializers
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.parsers import MultiPartParser, FormParser
from django.shortcuts import get_object_or_404
import os
from django.core.files.base import ContentFile
from django.core.files.storage import default_storage
from .tasks import import_guests_task # Importamos la tarea
from .models import Wedding, Invitation, Photo, Guest
from .serializers import (
    WeddingPublicSerializer, 
    InvitationPublicSerializer, 
    InvitationAdminSerializer,
    PhotoSerializer,
    GuestSerializer
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
        MAGIA DEL SAAS:
        El usuario no necesita enviar ?wedding_id=5.
        El sistema sabe quién es él y busca su boda automáticamente.
        """
        user = self.request.user
        
        # 1. Si eres tú (Superuser), ves TODO (útil para debuggear)
        if user.is_superuser:
            return Invitation.objects.all()
            
        # 2. Si es un Novio, buscamos SU boda
        try:
            # Gracias al OneToOneField y related_name='wedding'
            my_wedding = user.wedding 
            return Invitation.objects.filter(wedding=my_wedding)
        except Wedding.DoesNotExist:
            # Si el usuario existe pero no le asignaste boda todavía
            return Invitation.objects.none()
        
    def perform_create(self, serializer):
        """
        Interceptamos el guardado para asignar la boda automáticamente
        basada en el usuario que está haciendo la petición.
        """
        user = self.request.user
        
        # Opción A: Si eres un usuario normal (Novio) con boda asignada
        if hasattr(user, 'wedding'): 
            serializer.save(wedding=user.wedding)
            
        # Opción B: Si eres Superuser y NO tienes boda asignada (para evitar crash)
        elif user.is_superuser:
            # Aquí podrías decidir qué hacer. 
            # Si estás probando, asegúrate de que tu Superuser tenga una boda asignada 
            # o lanza un error amigable.
            raise serializers.ValidationError({"detail": "El superusuario no tiene una boda vinculada para crear invitaciones automáticamente."})

        else:
            raise serializers.ValidationError({"detail": "No tienes una boda asignada."})

    @action(detail=False, methods=['post'])
    def import_csv(self, request):
        file_obj = request.FILES.get('file')
        
        if not file_obj:
            return Response({"error": "No se envió ningún archivo"}, status=status.HTTP_400_BAD_REQUEST)

        try:
            # 1. Obtenemos la boda del usuario (Login required)
            user = request.user
            if user.is_superuser:
                 # Lógica para superuser (ej. recibir wedding_id por body o error)
                 return Response({"error": "Superuser debe especificar wedding_id manualmente (no implementado aquí)"}, status=400)
            
            wedding = user.wedding

            # 2. Guardamos el archivo temporalmente en el sistema de archivos
            # 'tmp/' se creará dentro de tu carpeta MEDIA_ROOT
            file_path = default_storage.save(f"tmp/{file_obj.name}", ContentFile(file_obj.read()))
            
            # Obtenemos la ruta absoluta del sistema operativo
            full_path = default_storage.path(file_path)

            # 3. Llamamos a la tarea de Celery pasando IDs y Rutas (Strings/Ints), no objetos
            import_guests_task.delay(wedding.id, full_path)
            
            return Response({"status": "El archivo se está procesando en segundo plano."}, status=status.HTTP_202_ACCEPTED)

        except Exception as e:
            return Response({"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
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
    

class GuestAdminViewSet(viewsets.ModelViewSet):
    """
    CRUD para gestionar las personas individuales dentro de una invitación.
    """
    serializer_class = GuestSerializer # Ya lo definimos antes en serializers.py
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        # Solo devolver guests que pertenezcan a la boda del usuario logueado
        user = self.request.user
        if user.is_superuser:
            return Guest.objects.all()
        
        # Filtramos por la boda del usuario
        if hasattr(user, 'wedding'):
            return Guest.objects.filter(invitation__wedding=user.wedding)
        
        return Guest.objects.none()

    def perform_create(self, serializer): 
        # Validamos que la invitación pertenezca a la boda del usuario
        invitation = serializer.validated_data['invitation']
        if not self.request.user.is_superuser:
            if invitation.wedding != self.request.user.wedding:
                raise serializers.ValidationError("No puedes agregar invitados a una boda ajena.")
        serializer.save()
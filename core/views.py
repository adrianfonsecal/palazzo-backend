from rest_framework import viewsets, mixins, status, permissions, serializers, generics
from django.contrib.auth.forms import UserCreationForm
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.parsers import MultiPartParser, FormParser
from rest_framework.throttling import AnonRateThrottle
from django.shortcuts import get_object_or_404
import os
from django.core.files.base import ContentFile
from django.core.files.storage import default_storage
from .tasks import import_guests_task, send_whatsapp_blast_task # Importamos la tarea
from .models import Wedding, Invitation, Photo, Guest, Lead
from .serializers import (
    PublicLeadSerializer,
    UserSerializer,
    WeddingPublicSerializer, 
    InvitationPublicSerializer, 
    InvitationAdminSerializer,
    PhotoSerializer,
    GuestSerializer,
    PublicLeadSerializer
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

    lookup_field = 'uuid'  # <--- Vital para que el update funcione con UUIDs

    def get_queryset(self):
        user = self.request.user
        
        if user.is_superuser:
            return Invitation.objects.all()
            
        try:
            my_wedding = user.wedding 
            return Invitation.objects.filter(wedding=my_wedding)
        except Wedding.DoesNotExist:
            return Invitation.objects.none()
        
    def perform_create(self, serializer):
    
        user = self.request.user
        
        
        if hasattr(user, 'wedding'): 
            serializer.save(wedding=user.wedding)
            
        
        elif user.is_superuser:
            raise serializers.ValidationError({"detail": "El superusuario no tiene una boda vinculada para crear invitaciones automáticamente."})

        else:
            raise serializers.ValidationError({"detail": "No tienes una boda asignada."})

    @action(detail=False, methods=['post'])
    def import_csv(self, request):
        file_obj = request.FILES.get('file')
        
        if not file_obj:
            return Response({"error": "No se envió ningún archivo"}, status=status.HTTP_400_BAD_REQUEST)

        try:
            
            user = request.user
            if user.is_superuser: 
                return Response({"error": "Superuser debe especificar wedding_id manualmente (no implementado aquí)"}, status=400)
            
            wedding = user.wedding

            file_path = default_storage.save(f"tmp/{file_obj.name}", ContentFile(file_obj.read()))
            
            full_path = default_storage.path(file_path)
            
            import_guests_task.delay(wedding.id, full_path)
            
            return Response({"status": "El archivo se está procesando en segundo plano."}, status=status.HTTP_202_ACCEPTED)

        except Exception as e:
            return Response({"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    @action(detail=False, methods=['post'])
    def send_blast(self, request):

        invitation_uuids = request.data.get('invitation_ids', [])
        
        if not invitation_uuids:
            return Response({"error": "No se seleccionaron invitaciones."}, status=400)

        if not request.user.is_superuser:
            user_wedding = request.user.wedding
            valid_count = Invitation.objects.filter(
                wedding=user_wedding, 
                uuid__in=invitation_uuids
            ).count()
            
            if valid_count != len(invitation_uuids):
                return Response({"error": "Algunas invitaciones no te pertenecen."}, status=403)

        send_whatsapp_blast_task.delay(invitation_uuids)

        return Response({
            "status": "Enviando mensajes...", 
            "count": len(invitation_uuids)
        }, status=200)

    @action(detail=False, methods=['post']) 
    def bulk_delete(self, request):

        invitation_uuids = request.data.get('invitation_uuids', [])
        
        if not invitation_uuids:
            return Response({"error": "No se enviaron IDs para eliminar."}, status=status.HTTP_400_BAD_REQUEST)

        user = request.user
        
        queryset = Invitation.objects.all()
        if not user.is_superuser:
            queryset = queryset.filter(wedding=user.wedding)

        deleted_count, _ = queryset.filter(uuid__in=invitation_uuids).delete()

        if deleted_count == 0:
            return Response({"warning": "No se borró nada. Verifica que los IDs sean correctos y te pertenezcan."}, status=status.HTTP_404_NOT_FOUND)

        return Response({"status": f"Se eliminaron {deleted_count} invitaciones correctamente."}, status=status.HTTP_200_OK)

# -----------------------------------------------------------------------------
# 5. VISTA Invitados / CRM (Para los Novios)
# -----------------------------------------------------------------------------
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

# -----------------------------------------------------------------------------
# 6. VISTA de Registro Usuario Django Admin (Para los Novios NO SUPERUSER)
# -----------------------------------------------------------------------------
class UserRegistrationViewSet(viewsets.GenericViewSet, mixins.CreateModelMixin):
    """
    Endpoint: POST /api/register/
    JSON Body: { "username": "...", "password": "...", "email": "...", "wedding_name": "Familia X" }
    """
    permission_classes = [permissions.AllowAny]
    serializer_class = UserSerializer # Usamos el serializer, no el Form

    # No necesitas sobreescribir def create() si usas el mixin y el serializer correctamente,
    # pero si quieres personalizar la respuesta:
    # def create(self, request, *args, **kwargs):
    #     serializer = self.get_serializer(data=request.data)
    #     serializer.is_valid(raise_exception=True)
    #     user = serializer.save()
        
    #     return Response({
    #         "status": "Usuario y Boda creados exitosamente.",
    #         "user_id": user.id,
    #         "wedding_id": user.wedding.id # Devolvemos esto para facilitar el frontend
    #     }, status=status.HTTP_201_CREATED)

# -----------------------------------------------------------------------------
# 6. VISTA de Registro LEADS (Para Captura de Interesados) ADMIN ONLY
# -----------------------------------------------------------------------------

class LeadCreateThrottle(AnonRateThrottle):
    rate = '5/minute' # Solo permite 5 intentos por minuto por IP

class PublicLeadCreateView(generics.CreateAPIView):
    """
    Endpoint PÚBLICO solo para CREAR leads (POST).
    Tiene protección contra spam masivo (Throttling).
    """
    queryset = Lead.objects.all()
    serializer_class = PublicLeadSerializer # Usamos el serializer con validaciones
    permission_classes = [permissions.AllowAny] # Abierto al público
    throttle_classes = [LeadCreateThrottle] # Protección contra ataques

# MANTÉN TU VISTA ANTERIOR PARA EL PANEL DE ADMIN (Solo lectura/gestión)
class LeadViewSet(viewsets.ModelViewSet):
    queryset = Lead.objects.all()
    serializer_class = PublicLeadSerializer
    permission_classes = [permissions.IsAuthenticated] # Solo tú puedes ver la lista
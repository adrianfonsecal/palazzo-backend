from rest_framework import serializers
from .models import Wedding, Invitation, Guest, Photo

# -----------------------------------------------------------------------------
# 1. SERIALIZERS DE INVITADOS (GUEST)
# -----------------------------------------------------------------------------

class GuestSerializer(serializers.ModelSerializer):
    """
    Serializa a cada persona individual.
    """
    class Meta:
        model = Guest
        fields = ['id', 'full_name', 'is_child', 'attendance', 'dietary_restrictions']
        # El ID es necesario para saber qué invitado específico estamos actualizando
        read_only_fields = ['id']
    
class InvitationAdminSerializer(serializers.ModelSerializer):
    """
    VISTA ADMIN (Para los novios/CRM).
    - Muestra TODO: teléfonos, emails, logs de envío.
    """
    guests = GuestSerializer(many=True, read_only=True)
    public_url = serializers.ReadOnlyField() # Usamos la propiedad del modelo

    class Meta:
        model = Invitation
        fields = '__all__'

# -----------------------------------------------------------------------------
# 2. SERIALIZER DE BODA (WEDDING)
# -----------------------------------------------------------------------------

class WeddingPublicSerializer(serializers.ModelSerializer):
    """
    Información solo de lectura para renderizar el Frontend (Colores, Mapa, Nombres).
    """
    class Meta:
        model = Wedding
        fields = ['slug', 'couple_names', 'event_date', 'location_name', 
                  'location_latitude', 'location_longitude', 'theme_config']
        read_only_fields = fields
    
# -----------------------------------------------------------------------------
# 3. SERIALIZERS DE INVITACIÓN (INVITATION + GUESTS)
# -----------------------------------------------------------------------------

class InvitationPublicSerializer(serializers.ModelSerializer):
    """
    VISTA PÚBLICA (Para el invitado).
    - Incluye los guests anidados (Nested).
    - Permite actualizar (RSVP) a todos los miembros de la familia de golpe.
    - Oculta datos sensibles como el teléfono o email.
    """
    guests = GuestSerializer(many=True) # Aquí ocurre la magia de la anidación
    wedding = WeddingPublicSerializer(read_only=True)

    class Meta:
        model = Invitation
        # Solo mostramos lo que el invitado necesita ver/editar
        #fields = ['uuid', 'family_name', 'status', 'guests', 'wedding', 'phone_number']
        fields = ['uuid', 'family_name', 'status', 'guests', 'wedding']
        read_only_fields = ['uuid', 'family_name']
         

    def update(self, instance, validated_data):
        """
        Lógica personalizada para permitir editar los invitados anidados
        cuando se hace un PATCH/PUT a la invitación principal.
        """
        guests_data = validated_data.pop('guests', [])
        
        # 1. Actualizamos el estado de la invitación principal (ej: a COMPLETED)
        instance.status = validated_data.get('status', instance.status)
        instance.save()

        # 2. Actualizamos a cada invitado individualmente
        for guest_data in guests_data:
            # Buscamos el invitado por ID dentro de esta invitación para seguridad
            # (evita que alguien edite un guest que no pertenece a esta familia)
            guest_id = guest_data.get('id')
            if guest_id:
                guest_obj = instance.guests.filter(id=guest_id).first()
                if guest_obj:
                    guest_obj.attendance = guest_data.get('attendance', guest_obj.attendance)
                    guest_obj.dietary_restrictions = guest_data.get('dietary_restrictions', guest_obj.dietary_restrictions)
                    guest_obj.save()
        
        return instance
    


# -----------------------------------------------------------------------------
# 4. SERIALIZER DE FOTOS
# -----------------------------------------------------------------------------

class PhotoSerializer(serializers.ModelSerializer):
    
    class Meta:
        model = Photo
        fields = ['id', 'image', 'caption', 'created_at', 'uploaded_by']
        read_only_fields = ['id', 'created_at', 'uploaded_by'] # El uploaded_by se pone automático en la View

    def validate_image(self, value):
        """
        Validación extra: Asegurar que no suban archivos gigantes o no-imágenes.
        """
        limit_mb = 5
        if value.size > limit_mb * 1024 * 1024:
            raise serializers.ValidationError(f"La imagen no puede pesar más de {limit_mb}MB.")
        return value
    
    
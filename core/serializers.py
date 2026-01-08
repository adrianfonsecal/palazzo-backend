
from rest_framework import serializers
from .models import Wedding, Invitation, Guest, Photo
from django.contrib.auth.models import User

# -----------------------------------------------------------------------------
# 1. SERIALIZERS DE INVITADOS (GUEST)
# -----------------------------------------------------------------------------

class GuestSerializer(serializers.ModelSerializer):
    # Definimos id explícitamente para que no sea read-only y pase a validated_data
    id = serializers.IntegerField(required=False) 

    class Meta:
        model = Guest
        fields = ['id', 'full_name', 'is_child', 'attendance', 'dietary_restrictions', 'invitation']
        read_only_fields = ['invitation'] # La invitación se infiere del padre
    
class InvitationAdminSerializer(serializers.ModelSerializer):
    guests = GuestSerializer(many=True, required=False) 
    public_url = serializers.ReadOnlyField()

    class Meta:
        model = Invitation
        fields = '__all__'
        read_only_fields = ['id', 'uuid', 'wedding', 'last_sent_at', 'whatsapp_message_id']

    def update(self, instance, validated_data):
        
        guests_data = validated_data.pop('guests', [])
        
        instance = super().update(instance, validated_data)
        
        for guest_data in guests_data:
            guest_id = guest_data.get('id')

            if guest_id:

                guest_obj = Guest.objects.filter(id=guest_id, invitation=instance).first()
                if guest_obj:
                    guest_obj.full_name = guest_data.get('full_name', guest_obj.full_name)
                    guest_obj.is_child = guest_data.get('is_child', guest_obj.is_child)
                    guest_obj.attendance = guest_data.get('attendance', guest_obj.attendance)
                    guest_obj.dietary_restrictions = guest_data.get('dietary_restrictions', guest_obj.dietary_restrictions)
                    guest_obj.save()
            else:
                Guest.objects.create(invitation=instance, **guest_data)

        return instance
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

    guests = GuestSerializer(many=True) # Aquí ocurre la magia de la anidación
    wedding = WeddingPublicSerializer(read_only=True)

    class Meta:
        model = Invitation
        # Solo mostramos lo que el invitado necesita ver/editar
        #fields = ['uuid', 'family_name', 'status', 'guests', 'wedding', 'phone_number']
        fields = ['uuid', 'family_name', 'status', 'guests', 'wedding', 'phone_number']
        read_only_fields = ['uuid', ]
         

    def update(self, instance, validated_data):

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
    
# -----------------------------------------------------------------------------
# 5. SERIALIZER DE USUARIOS (DJANGO ADMIN)
# -----------------------------------------------------------------------------

class UserSerializer(serializers.ModelSerializer):
    slug = serializers.CharField(write_only=True, required=True)
    claim_code = serializers.CharField(write_only=True, required=True)
    
    password = serializers.CharField(write_only=True)

    class Meta:
        model = User
        fields = ['id', 'username', 'email', 'password', 'slug', 'claim_code']
        read_only_fields = ['id']

    def validate(self, data):

        slug = data.get('slug')
        claim_code = data.get('claim_code')

        try:
            wedding = Wedding.objects.get(slug=slug, claim_code=claim_code)
            
            if wedding.owner is not None:
                raise serializers.ValidationError({
                    "claim_code": "Esta boda ya ha sido reclamada por otro usuario."
                })
            
            self.context['target_wedding'] = wedding

        except Wedding.DoesNotExist:
            raise serializers.ValidationError({
                "claim_code": "El identificador (Slug) o el Código de Reclamación son incorrectos."
            })

        return data

    def create(self, validated_data):

        validated_data.pop('slug')
        validated_data.pop('claim_code')
        
        user = User.objects.create_user(**validated_data)
        
        wedding = self.context['target_wedding']
        
        wedding.owner = user
        wedding.save()
        
        return user
import uuid
from django.db import models
from django.utils.translation import gettext_lazy as _
from django.conf import settings
from django.contrib.auth.models import User

# -----------------------------------------------------------------------------
# 1. MODELO TENANT (La Boda)
# -----------------------------------------------------------------------------
class Wedding(models.Model):
    """
    Representa una boda (Tenant). Todos los datos del sistema 
    (invitados, fotos) deben pertenecer a una instancia de Wedding.
    """
    # Información General
    slug = models.SlugField(unique=True, help_text="Identificador para la URL, ej: 'juan-y-maria'")
    couple_names = models.CharField(max_length=255, help_text="Ej: Juan y María")
    event_date = models.DateTimeField()
    
    # Configuración de Ubicación (Google Maps)
    location_name = models.CharField(max_length=255, blank=True)
    location_latitude = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)
    location_longitude = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)
    
    # Configuración Visual (JSON para flexibilidad)
    # Aquí guardas: {"primary_color": "#FF0000", "font": "Roboto", "welcome_msg": "..."}
    theme_config = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    
    # RELACIÓN CON EL USUARIO (NOVIO/A)
    # OneToOneField asegura que un usuario solo tenga UNA boda asignada (Simplifica la lógica)
    owner = models.OneToOneField(
        User,
        on_delete=models.CASCADE, 
        related_name='wedding',
        null=True,   # <--- PERMITE QUE LA BODA NAZCA SIN DUEÑO
        blank=True
    )
    
    claim_code = models.CharField(max_length=10, blank=True, null=True, help_text="Código secreto para reclamar la boda")

    def __str__(self):
        return f"Boda de {self.couple_names}"

# -----------------------------------------------------------------------------
# 2. MODELO INVITACIÓN (Agrupador / Cabeza de Familia)
# -----------------------------------------------------------------------------
class Invitation(models.Model):
    """
    Agrupa a una familia o pareja. Es la entidad que recibe el WhatsApp
    y posee el Link único.
    """
    class Status(models.TextChoices):
        PENDING = 'PENDING', _('Pendiente de Envío')
        SENT = 'SENT', _('Enviado por WhatsApp')
        DELIVERED = 'DELIVERED', _('Entregado')
        OPENED = 'OPENED', _('Visto por el invitado')
        COMPLETED = 'COMPLETED', _('Confirmación Completada')

    wedding = models.ForeignKey(Wedding, on_delete=models.CASCADE, related_name='invitations')
    
    # SEGURIDAD: Este UUID es el que va en la URL pública.
    # unique=True es vital para que no haya colisiones.
    uuid = models.UUIDField(default=uuid.uuid4, editable=False, unique=True)
    
    # Datos de Contacto (Solo del titular)
    family_name = models.CharField(max_length=150, help_text="Ej: Familia Pérez o Juan y Acompañante")
    phone_number = models.CharField(max_length=20, help_text="Formato E.164 para WhatsApp (ej: +521...)")
    email = models.EmailField(blank=True, null=True)
    
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.PENDING)
    last_sent_at = models.DateTimeField(null=True, blank=True)

    whatsapp_message_id = models.CharField(max_length=100, blank=True, null=True, unique=True)
    
    def __str__(self):
        return f"{self.family_name} ({self.get_status_display()})"

    @property
    def public_url(self):
        # Propiedad helper para obtener el link rápido en el template
        # Asumiendo que configuras el dominio en settings
        return f"https://app.palazzoinvites.com/invitacion/{self.uuid}"

# -----------------------------------------------------------------------------
# 3. MODELO INVITADO (Personas Individuales)
# -----------------------------------------------------------------------------
class Guest(models.Model):
    """
    Cada persona física dentro de una invitación. 
    Se usa para el conteo de platos y restricciones.
    """
    class Attendance(models.TextChoices):
        PENDING = 'PENDING', _('Sin Confirmar')
        ACCEPTED = 'ACCEPTED', _('Asistiré')
        DECLINED = 'DECLINED', _('No Asistiré')

    invitation = models.ForeignKey(Invitation, on_delete=models.CASCADE, related_name='guests')
    
    full_name = models.CharField(max_length=150)
    is_child = models.BooleanField(default=False, help_text="¿Requiere menú de niños?")
    
    attendance = models.CharField(max_length=20, choices=Attendance.choices, default=Attendance.PENDING)
    dietary_restrictions = models.TextField(blank=True, help_text="Alergias, vegetariano, etc.")

    def __str__(self):
        return f"{self.full_name} - {self.get_attendance_display()}"

# -----------------------------------------------------------------------------
# 4. MODELO FOTOS (Álbum Colaborativo)
# -----------------------------------------------------------------------------
class Photo(models.Model):
    wedding = models.ForeignKey(Wedding, on_delete=models.CASCADE, related_name='photos')
    
    # Rastreabilidad: Saber qué invitación subió la foto (Seguridad)
    uploaded_by = models.ForeignKey(Invitation, on_delete=models.SET_NULL, null=True, blank=True)
    
    # Al usar django-storages con S3, este campo guarda automáticamente la URL de S3
    image = models.ImageField(upload_to='wedding_photos/%Y/%m/%d/')
    
    caption = models.CharField(max_length=255, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    is_approved = models.BooleanField(default=True, help_text="Desmarcar para ocultar fotos inapropiadas")

    def __str__(self):
        return f"Foto {self.id} - {self.wedding.slug}"
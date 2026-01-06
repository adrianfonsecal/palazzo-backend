from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.contrib.auth.models import User
from .models import Wedding

# 1. Definimos el "Inline".
# Esto le dice a Django: "Muestra el formulario de Wedding DENTRO del formulario de User"
class WeddingInline(admin.StackedInline):
    model = Wedding
    can_delete = False
    verbose_name_plural = 'Configuración de la Boda'
    fk_name = 'owner' # Importante: indica cuál es el campo que une ambos modelos
    
    # Opcional: Si quieres que sea obligatorio llenar esto al crear el usuario
    min_num = 1 
    max_num = 1

# 2. Extendemos el UserAdmin oficial de Django
class UserAdmin(BaseUserAdmin):
    inlines = (WeddingInline,)
    
    # Configuración visual para listar usuarios y ver rápido si tienen boda
    list_display = ('username', 'email', 'get_couple_names', 'get_wedding_slug', 'is_staff')
    
    def get_couple_names(self, instance):
        # Manejo de error por si el usuario aún no tiene boda (ej. superusuario)
        return instance.wedding.couple_names if hasattr(instance, 'wedding') else '-'
    get_couple_names.short_description = 'Pareja'

    def get_wedding_slug(self, instance):
        return instance.wedding.slug if hasattr(instance, 'wedding') else '-'
    get_wedding_slug.short_description = 'Slug / URL'

# 3. Re-registramos el User Admin
admin.site.unregister(User)
admin.site.register(User, UserAdmin)

# 4. Registramos Wedding por si acaso quieres verlas por separado también
@admin.register(Wedding)
class WeddingAdmin(admin.ModelAdmin):
    list_display = ('couple_names', 'slug', 'event_date', 'owner')
    search_fields = ('couple_names', 'slug', 'owner__username')

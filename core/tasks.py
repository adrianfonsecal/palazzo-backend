import pandas as pd
import requests
import logging
from celery import shared_task
from django.db import transaction
from django.conf import settings
from .models import Wedding, Invitation, Guest
import os

# Configuramos un logger para ver errores en la consola de Celery
logger = logging.getLogger(__name__)

# -----------------------------------------------------------------------------
# TAREA 1: IMPORTACIÓN MASIVA (CSV / EXCEL)
# -----------------------------------------------------------------------------
@shared_task
def import_guests_task(wedding_id, file_path):
    try:
        
        if file_path.endswith('.csv'):
            df = pd.read_csv(file_path)
        else:
            df = pd.read_excel(file_path)

        
        df.columns = [c.strip().lower().replace(' ', '_') for c in df.columns]
        
        required_cols = ['telefono', 'nombre_invitado']
        if not all(col in df.columns for col in required_cols):
            return f"Error: Faltan columnas. Se requiere al menos: {required_cols}"

        guests_created = 0
        invitations_created = 0

        with transaction.atomic():
            wedding = Wedding.objects.get(id=wedding_id)

            for phone, rows in df.groupby('telefono'):
                
                first_row = rows.iloc[0]
                family_name = first_row.get('nombre_familia', f"Familia {first_row['nombre_invitado']}")
                email = first_row.get('email', None)
                
                invitation, created = Invitation.objects.update_or_create(
                    wedding=wedding,
                    phone_number=str(phone),
                    defaults={
                        'family_name': family_name,
                        'email': email if pd.notna(email) else ""
                    }
                )
                if created:
                    invitations_created += 1

                for _, row in rows.iterrows():
                    guest_list = row["nombre_invitado"].split(',')
                    for guest_name in guest_list:
                        Guest.objects.create(
                            invitation=invitation,
                            full_name=guest_name.strip(),
                            is_child=bool(row.get('es_nino', False))
                        )
                        guests_created += 1
        

        if os.path.exists(file_path):
            os.remove(file_path)
        logger.info(f"Importación exitosa: {invitations_created} invitaciones, {guests_created} invitados.")
        return f"Procesado: {invitations_created} invitaciones, {guests_created} personas."

    except Exception as e:
        if os.path.exists(file_path):
            os.remove(file_path)
        logger.error(f"Error importando archivo para boda {wedding_id}: {str(e)}")
        return f"Error crítico: {str(e)}"


# -----------------------------------------------------------------------------
# TAREA 2: ENVÍO MASIVO WHATSAPP
# -----------------------------------------------------------------------------
@shared_task
def send_whatsapp_blast_task(invitation_uuids
                             ):
    """
    Envía WhatsApps solo a la lista de UUIDs recibida.
    """
    # Buscamos las invitaciones en la BD que coincidan con la lista
    # y que NO hayan sido enviadas (doble check de seguridad)
    invitations_to_send = Invitation.objects.filter(
        uuid__in=invitation_uuids,
        status=Invitation.Status.PENDING # Opcional: permitir reenvío quitando esto
    )

    sent_count = 0
    errors = []
    
    for invite in invitations_to_send:
        try:
            # 1. Construir el mensaje
            # Meta requiere plantillas pre-aprobadas. Supongamos una llamada "boda_invitacion_v1"
            # Variables: {{1}} = Nombre Familia, {{2}} = Link
            
            payload = {
                "messaging_product": "whatsapp",
                "to": invite.phone_number,
                "type": "template",
                "template": {
                    "name": "boda_invitacion_v1", # Nombre configurado en Facebook Business
                    "language": {"code": "es"},
                    "components": [
                        {
                            "type": "body",
                            "parameters": [
                                {"type": "text", "text": invite.family_name},  # Variable {{1}}
                                {"type": "text", "text": invite.public_url}    # Variable {{2}} (El Link UUID)
                            ]
                        }
                    ]
                }
            }

            # 2. Enviar a la API de Meta
            response = requests.post(
                url=f"https://graph.facebook.com/v17.0/{settings.META_PHONE_ID}/messages",
                headers={
                    "Authorization": f"Bearer {settings.META_ACCESS_TOKEN}",
                    "Content-Type": "application/json"
                },
                json=payload,
                timeout=10 # Timeout para no colgar el worker
            )

            # 3. Actualizar estado según respuesta
            if response.status_code in [200, 201]:
                invite.status = Invitation.Status.SENT
                invite.last_sent_at = pd.Timestamp.now()
                invite.save()
                sent_count += 1
            else:
                logger.error(f"Fallo al enviar a {invite.phone_number}: {response.text}")
            

        except Exception as e:
            logger.error(f"Error enviando a {invite.uuid}: {e}")
            errors.append(str(e))
            continue # Si falla uno, seguimos con el siguiente

    return f"Procesado: {sent_count} enviados. Errores: {len(errors)}"
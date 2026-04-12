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
    print("Iniciando importación de invitados...")
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
                    nombre_invitado = row.get("nombre_invitado")
                    if pd.isna(nombre_invitado) or str(nombre_invitado).strip() == "":
                        continue

                    guest_list = str(nombre_invitado).split(',')
                    for guest_name in guest_list:
                        guest_name_clean = guest_name.strip()
                        if guest_name_clean:
                            Guest.objects.create(
                                invitation=invitation,
                                full_name=guest_name_clean,
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
def send_whatsapp_blast_task(invitation_uuids):

    invitations = Invitation.objects.filter(uuid__in=invitation_uuids)
    
    results = {
        "success": 0,
        "failed": 0,
        "errors": []
    }
    url = f"https://graph.facebook.com/v23.0/963271596861809/messages"
    headers = {
        "Authorization": f"Bearer EAANLS1fqZBcsBQr7IdpK83ZB6VtlTxvvNwNvD6tg3L3mUChGypVlW0GwT8W9bz6ipigLbY6DZBS1WBNr336FGqwWYkDkCJkFZAUr1AUGL08gzNA8ZBA6wjKKUeI55gksoStrCMxoXwZAyAoZBBgla39AQZBmS8BnsxC3jF4UJfk2o9v1ZAyS5iNPdJHx9woINVxWS4tYiPb9AobMUPtUz4SVDURj7i93UQIaMeeDUoNQp",
        "Content-Type": "application/json"
    }

    for invite in invitations:
        try:
            payload = {
                "messaging_product": "whatsapp",
                "recipient_type": "individual",
                "to": invite.phone_number,
                "type": "template",
                "template": {
                    "name": "mensaje_invitacion",
                    "language": {
                        "code": "en"
                    },
                    "components": [
                        {
                            "type": "header",
                            "parameters": [
                                {
                                    "type": "image",
                                    "parameter_name": "imagen_boda",
                                    "image": {
                                        "id": "2387781248333171"
                                    }
                                }
                            ]
                        },
                        {
                            "type": "body",
                            "parameters": [
                                {
                                    "type": "text",
                                    "parameter_name": "nombre",
                                    "text": invite.family_name
                                },
                                {
                                    "type": "text",
                                    "parameter_name": "nombre_boda",
                                    "text": invite.wedding.couple_names
                                }
                            ]
                        },
                        {
                            "type": "button",
                            "sub_type": "url",
                            "index": 0,
                            "parameters": [
                                {
                                    "type": "text",
                                    "text": str(invite.uuid)
                                }
                            ]
                        }
                    ]
                }
            }
            print(payload)

            
            
            # 3. Enviar
            response = requests.post(url, json=payload, headers=headers, timeout=10)
            data = response.json()
            #print(f"Respuesta WhatsApp para {invite.phone_number}: {data}")
             
            if response.status_code in [200, 201]:
                wamid = data.get('messages', [{}])[0].get('id')
                invite.whatsapp_message_id = wamid # <--- GUARDAMOS EL ID
                invite.status = 'SENT' 
                invite.save()
                results["success"] += 1
            else:
                error_msg = data.get('error', {}).get('message', 'Unknown error')
                logger.error(f"Fallo WhatsApp {invite.phone_number}: {error_msg}")
                results["failed"] += 1
                results["errors"].append(f"{invite.phone_number}: {error_msg}")

        except Exception as e:
            logger.error(f"Error crítico enviando a {invite.uuid}: {str(e)}")
            results["failed"] += 1
            results["errors"].append(str(e))

    return f"WhatsApp Blast finalizado. Éxitos: {results['success']}, Fallos: {results['failed']}"
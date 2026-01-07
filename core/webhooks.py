from django.http import HttpResponse, JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
import json
from .models import Invitation

VERIFY_TOKEN = "PALAZZO_SECRET_TOKEN_123" 

@csrf_exempt
def whatsapp_webhook(request):
    
    if request.method == 'GET':
        mode = request.GET.get('hub.mode')
        token = request.GET.get('hub.verify_token')
        challenge = request.GET.get('hub.challenge')

        if mode == 'subscribe' and token == VERIFY_TOKEN:
            return HttpResponse(challenge, status=200)
        else:
            return HttpResponse('Forbidden', status=403)

    elif request.method == 'POST':
        try:
            body = json.loads(request.body)
            print(body)
            entry = body.get('entry', [])[0]
            changes = entry.get('changes', [])[0]
            value = changes.get('value', {})
            statuses = value.get('statuses', [])

            if statuses:
                status_update = statuses[0]
                wamid = status_update.get('id')
                new_status_meta = status_update.get('status') 

                status_map = {
                    'delivered': Invitation.Status.DELIVERED,
                    'read': Invitation.Status.OPENED,
                    'failed': 'FAILED' 
                }

                if new_status_meta in status_map:
                    try:
                        invite = Invitation.objects.get(whatsapp_message_id=wamid)
                        
                        current_weight = get_status_weight(invite.status)
                        new_weight = get_status_weight(status_map[new_status_meta])

                        if new_weight > current_weight:
                            invite.status = status_map[new_status_meta]
                            invite.save()
                            print(f"Estado actualizado: {invite.family_name} -> {new_status_meta}")

                    except Invitation.DoesNotExist:
                        pass 

            return HttpResponse('EVENT_RECEIVED', status=200)
        
        except Exception as e:
            print(f"Error webhook: {e}")
            return HttpResponse('ERROR', status=500)

def get_status_weight(status):
    weights = {
        'PENDING': 0,
        'SENT': 1,
        'DELIVERED': 2,
        'OPENED': 3,
    }
    return weights.get(status, 0)
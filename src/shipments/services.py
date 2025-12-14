import hashlib
import hmac
import json
import logging
from datetime import datetime

import requests
from django.conf import settings

from .models import Webhook, Shipment

logger = logging.getLogger(__name__)


def generate_webhook_signature(secret: str, payload: str) -> str:
    """Generate HMAC-SHA256 signature for webhook payload."""
    return hmac.new(
        secret.encode('utf-8'),
        payload.encode('utf-8'),
        hashlib.sha256
    ).hexdigest()


def send_webhook_notification(shipment: Shipment, event: str):
    """
    Send webhook notifications to all registered URLs for the given event.
    
    Args:
        shipment: The Shipment instance that triggered the event
        event: The event type (e.g., 'shipment.status_changed')
    """
    # Get all active webhooks for this user and event
    webhooks = Webhook.objects.filter(
        user=shipment.user,
        event=event,
        is_active=True
    )
    
    if not webhooks.exists():
        return
    
    # Prepare the payload
    payload = {
        'event': event,
        'tracking_number': shipment.tracking_number,
        'new_status': shipment.status,
        'reference_number': shipment.reference_number,
        'shipment_id': str(shipment.id),
        'timestamp': datetime.utcnow().isoformat() + 'Z'
    }
    
    payload_json = json.dumps(payload)
    
    # Send to each registered webhook
    for webhook in webhooks:
        try:
            headers = {
                'Content-Type': 'application/json',
                'X-Webhook-Event': event,
            }
            
            # Add signature if secret is set
            if webhook.secret:
                signature = generate_webhook_signature(webhook.secret, payload_json)
                headers['X-Webhook-Signature'] = signature
            
            response = requests.post(
                webhook.url,
                data=payload_json,
                headers=headers,
                timeout=10  # 10 second timeout
            )
            
            if response.status_code >= 200 and response.status_code < 300:
                logger.info(f"Webhook sent successfully to {webhook.url} for {event}")
            else:
                logger.warning(
                    f"Webhook to {webhook.url} returned status {response.status_code}"
                )
                
        except requests.exceptions.Timeout:
            logger.error(f"Webhook timeout for {webhook.url}")
        except requests.exceptions.RequestException as e:
            logger.error(f"Webhook failed for {webhook.url}: {str(e)}")


def update_shipment_status(shipment: Shipment, new_status: str, description: str = None, location: str = ''):
    """
    Update shipment status. Webhooks are triggered automatically via signals.
    
    Args:
        shipment: The Shipment instance to update
        new_status: The new status value
        description: Optional description for the tracking event
        location: Optional location for the tracking event
    """
    from .models import TrackingEvent
    
    old_status = shipment.status
    shipment.status = new_status
    shipment.save()  # This triggers the signal which sends webhooks
    
    # Create tracking event
    TrackingEvent.objects.create(
        shipment=shipment,
        status=new_status,
        description=description or f"Status changed from {old_status} to {new_status}",
        location=location
    )

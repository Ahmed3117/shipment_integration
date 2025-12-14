from django.db.models.signals import pre_save, post_save
from django.dispatch import receiver

from .models import Shipment, TrackingEvent


@receiver(pre_save, sender=Shipment)
def track_status_change(sender, instance, **kwargs):
    """
    Track the old status before saving to detect changes.
    """
    if instance.pk:
        try:
            old_instance = Shipment.objects.get(pk=instance.pk)
            instance._old_status = old_instance.status
        except Shipment.DoesNotExist:
            instance._old_status = None
    else:
        instance._old_status = None


@receiver(post_save, sender=Shipment)
def handle_status_change(sender, instance, created, **kwargs):
    """
    Automatically send webhook notifications when shipment status changes.
    """
    from .services import send_webhook_notification
    
    # For new shipments
    if created:
        send_webhook_notification(instance, 'shipment.created')
        return
    
    # For status updates
    old_status = getattr(instance, '_old_status', None)
    new_status = instance.status
    
    if old_status and old_status != new_status:
        # Status has changed - send webhook
        send_webhook_notification(instance, 'shipment.status_changed')
        
        # Send specific event for delivered
        if new_status == 'delivered':
            send_webhook_notification(instance, 'shipment.delivered')

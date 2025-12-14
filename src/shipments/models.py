import uuid
from django.db import models
from django.conf import settings


class Address(models.Model):
    """Model to store addresses for shipments."""
    name = models.CharField(max_length=255)
    street = models.CharField(max_length=500)
    city = models.CharField(max_length=100)
    state = models.CharField(max_length=100)
    zip_code = models.CharField(max_length=20)
    country = models.CharField(max_length=100, default='USA')
    phone = models.CharField(max_length=20)
    
    class Meta:
        db_table = 'addresses'
        verbose_name_plural = 'Addresses'
    
    def __str__(self):
        return f"{self.name} - {self.city}, {self.state}"


class ServiceType(models.Model):
    """Shipping service types."""
    name = models.CharField(max_length=100, unique=True)  # e.g., Standard, Express
    code = models.CharField(max_length=50, unique=True)
    base_rate = models.DecimalField(max_digits=10, decimal_places=2)
    rate_per_kg = models.DecimalField(max_digits=10, decimal_places=2)
    estimated_days_min = models.PositiveIntegerField()
    estimated_days_max = models.PositiveIntegerField()
    is_active = models.BooleanField(default=True)
    
    class Meta:
        db_table = 'service_types'
    
    def __str__(self):
        return self.name


class Shipment(models.Model):
    """Main shipment model."""
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('confirmed', 'Confirmed'),
        ('picked_up', 'Picked Up'),
        ('in_transit', 'In Transit'),
        ('out_for_delivery', 'Out for Delivery'),
        ('delivered', 'Delivered'),
        ('cancelled', 'Cancelled'),
        ('returned', 'Returned'),
    ]
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='shipments')
    tracking_number = models.CharField(max_length=50, unique=True, blank=True)
    reference_number = models.CharField(max_length=100, blank=True, help_text='Customer order ID')
    
    # Addresses
    sender_address = models.ForeignKey(Address, on_delete=models.PROTECT, related_name='sent_shipments')
    receiver_address = models.ForeignKey(Address, on_delete=models.PROTECT, related_name='received_shipments')
    
    # Package details
    weight = models.DecimalField(max_digits=10, decimal_places=2, help_text='Weight in kg')
    length = models.DecimalField(max_digits=10, decimal_places=2, help_text='Length in cm')
    width = models.DecimalField(max_digits=10, decimal_places=2, help_text='Width in cm')
    height = models.DecimalField(max_digits=10, decimal_places=2, help_text='Height in cm')
    content_description = models.TextField(blank=True)
    
    # Service and pricing
    service_type = models.ForeignKey(ServiceType, on_delete=models.PROTECT)
    estimated_cost = models.DecimalField(max_digits=10, decimal_places=2)
    estimated_delivery_date = models.DateField(null=True, blank=True)
    
    # Status
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    
    # Label
    label_url = models.URLField(blank=True)
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'shipments'
        ordering = ['-created_at']
    
    def save(self, *args, **kwargs):
        if not self.tracking_number:
            self.tracking_number = self.generate_tracking_number()
        super().save(*args, **kwargs)
    
    def generate_tracking_number(self):
        import random
        prefix = 'SHP'
        random_part = ''.join([str(random.randint(0, 9)) for _ in range(12)])
        return f"{prefix}{random_part}"
    
    def __str__(self):
        return f"{self.tracking_number} - {self.status}"


class TrackingEvent(models.Model):
    """Tracking events for shipments."""
    shipment = models.ForeignKey(Shipment, on_delete=models.CASCADE, related_name='tracking_events')
    status = models.CharField(max_length=50)
    description = models.TextField(blank=True, null=True)
    location = models.CharField(max_length=255, blank=True)
    timestamp = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        db_table = 'tracking_events'
        ordering = ['-timestamp']
    
    def __str__(self):
        return f"{self.shipment.tracking_number} - {self.status}"


class Webhook(models.Model):
    """Webhook registration for status updates."""
    EVENT_CHOICES = [
        ('shipment.status_changed', 'Shipment Status Changed'),
        ('shipment.created', 'Shipment Created'),
        ('shipment.delivered', 'Shipment Delivered'),
    ]
    
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='webhooks')
    url = models.URLField()
    event = models.CharField(max_length=50, choices=EVENT_CHOICES)
    is_active = models.BooleanField(default=True)
    secret = models.CharField(max_length=100, blank=True, help_text='Secret for webhook signature')
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        db_table = 'webhooks'
        unique_together = ['user', 'url', 'event']
    
    def __str__(self):
        return f"{self.user.username} - {self.event}"

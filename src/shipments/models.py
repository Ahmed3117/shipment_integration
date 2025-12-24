import uuid
import secrets
from django.db import models
from django.conf import settings


class Address(models.Model):
    """Model to store addresses for shipments."""
    name = models.CharField(max_length=255)
    street = models.CharField(max_length=500)
    city = models.CharField(max_length=100)
    state = models.CharField(max_length=100)
    zip_code = models.CharField(max_length=20)
    country = models.CharField(max_length=100, default='Egypt')
    phone = models.CharField(max_length=20)
    
    class Meta:
        db_table = 'addresses'
        verbose_name_plural = 'Addresses'
    
    def __str__(self):
        return f"{self.name} - {self.city}, {self.state}"


class ServiceType(models.Model):
    """Shipping service types - can be company-specific or global."""
    company = models.ForeignKey(
        'accounts.Company',
        on_delete=models.CASCADE,
        related_name='service_types',
        help_text='Company this service type belongs to'
    )
    name = models.CharField(max_length=100)  # e.g., Standard, Express
    code = models.CharField(max_length=50)
    base_rate = models.DecimalField(max_digits=10, decimal_places=2)
    rate_per_kg = models.DecimalField(max_digits=10, decimal_places=2)
    estimated_days_min = models.PositiveIntegerField()
    estimated_days_max = models.PositiveIntegerField()
    is_active = models.BooleanField(default=True)
    
    class Meta:
        db_table = 'service_types'
        # Unique name and code per company
        unique_together = [
            ['company', 'name'],
            ['company', 'code'],
        ]
    
    def __str__(self):
        return f"{self.company.name} - {self.name}"


class Shipment(models.Model):
    """Main shipment model."""
    STATUS_CHOICES = [
        ('created', 'Created'),
        ('picked_up', 'Picked Up'),
        ('in_transit', 'In Transit'),
        ('out_for_delivery', 'Out for Delivery'),
        ('delivered', 'Delivered'),
        ('cancelled', 'Cancelled'),
        ('returned', 'Returned'),
    ]
    
    # id = models.BigAutoField(primary_key=True)  # Default BigAutoField
    
    # Company relationship
    company = models.ForeignKey(
        'accounts.Company',
        on_delete=models.CASCADE,
        related_name='shipments',
        help_text='The company that created this shipment'
    )
    
    # Carrier assignment
    carrier = models.ForeignKey(
        settings.AUTH_USER_MODEL, 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True, 
        related_name='carrier_shipments',
        help_text='Assigned carrier for this shipment'
    )
    
    tracking_number = models.CharField(max_length=20, unique=True, blank=True)
    reference_number = models.CharField(max_length=100, blank=True, help_text='Customer order ID')
    
    # Addresses - sender is nullable (can use company default address)
    sender_address = models.ForeignKey(
        Address, 
        on_delete=models.PROTECT, 
        related_name='sent_shipments',
        null=True,
        blank=True,
        help_text='Sender address. If null, company address may be used.'
    )
    receiver_address = models.ForeignKey(
        Address, 
        on_delete=models.PROTECT, 
        related_name='received_shipments'
    )
    
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
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='created')
    
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
        # 10 numeric digits
        return ''.join([str(random.randint(0, 9)) for _ in range(10)])
    
    def __str__(self):
        return f"{self.tracking_number} - {self.status}"


class TrackingEvent(models.Model):
    """Tracking events for shipments."""
    shipment = models.ForeignKey(Shipment, on_delete=models.CASCADE, related_name='tracking_events')
    status = models.CharField(max_length=50)
    description = models.TextField(blank=True, null=True)
    location = models.CharField(max_length=255, blank=True, null=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='tracking_events',
        help_text='User (carrier/admin) who created this event'
    )
    timestamp = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        db_table = 'tracking_events'
        ordering = ['-timestamp']
    
    def __str__(self):
        return f"{self.shipment.tracking_number} - {self.status}"


def generate_webhook_secret():
    """Generate a simple secret for webhook validation."""
    return secrets.token_hex(16)


class Webhook(models.Model):
    """
    Webhook registration for shipment status updates.
    When a shipment status changes, a POST request is sent to the URL
    with the new status and the secret for validation.
    """
    company = models.ForeignKey(
        'accounts.Company',
        on_delete=models.CASCADE,
        related_name='webhooks',
        help_text='The company that registered this webhook'
    )
    url = models.URLField(help_text='URL to receive webhook POST requests')
    secret = models.CharField(
        max_length=64, 
        default=generate_webhook_secret,
        help_text='Secret sent with each webhook for validation'
    )
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'webhooks'
        # One webhook URL per company
        unique_together = ['company', 'url']
    
    def regenerate_secret(self):
        """Generate a new secret for this webhook."""
        self.secret = generate_webhook_secret()
        self.save(update_fields=['secret', 'updated_at'])
        return self.secret
    
    def __str__(self):
        return f"{self.company.name} - {self.url}"

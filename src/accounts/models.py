from django.contrib.auth.models import AbstractUser
from django.db import models


class User(AbstractUser):
    """Custom user model for the shipping platform."""
    USER_TYPE_CHOICES = [
        ('customer', 'Customer'),
        ('carrier', 'Carrier'),
        ('admin', 'Admin'),
    ]
    
    user_type = models.CharField(max_length=20, choices=USER_TYPE_CHOICES, default='customer')
    company_name = models.CharField(max_length=255, blank=True)
    phone = models.CharField(max_length=20, blank=True)
    
    # Company approval status - customers need admin approval before they can use the API
    is_approved = models.BooleanField(
        default=False,
        help_text='Designates whether this company account has been approved by admin. '
                  'Customers must be approved before they can login and use the API.'
    )
    approved_at = models.DateTimeField(null=True, blank=True)
    approved_by = models.ForeignKey(
        'self',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='approved_users',
        help_text='Admin who approved this account'
    )
    rejection_reason = models.TextField(
        blank=True,
        help_text='Reason for rejection if account was not approved'
    )
    
    class Meta:
        db_table = 'users'
    
    @property
    def is_carrier(self):
        return self.user_type == 'carrier'
    
    @property
    def is_customer(self):
        return self.user_type == 'customer'
    
    @property
    def can_access_api(self):
        """Check if user can access the API (active and approved if customer)."""
        if not self.is_active:
            return False
        # Admins and carriers don't need approval
        if self.user_type in ['admin', 'carrier']:
            return True
        # Customers need approval
        return self.is_approved
    
    def __str__(self):
        return self.email or self.username

import secrets
from django.contrib.auth.models import AbstractUser
from django.db import models


def generate_company_token():
    """Generate a secure random token for company API authentication."""
    return f"comp_{secrets.token_hex(32)}"


class Company(models.Model):
    """
    Company model representing e-commerce businesses that use the shipping API.
    Each company has a unique token for API authentication.
    """
    name = models.CharField(max_length=255, unique=True)
    email = models.EmailField(unique=True)
    phone = models.CharField(max_length=20, blank=True)
    address = models.TextField(blank=True, help_text='Company headquarters address')
    
    # API Authentication
    token = models.CharField(
        max_length=100, 
        unique=True, 
        default=generate_company_token,
        help_text='API token for company authentication. Send in X-Company-Token header.'
    )
    
    # Status
    is_active = models.BooleanField(default=True, help_text='Whether this company can use the API')
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'companies'
        verbose_name_plural = 'Companies'
        ordering = ['name']
    
    def regenerate_token(self):
        """Generate a new API token for this company."""
        self.token = generate_company_token()
        self.save(update_fields=['token', 'updated_at'])
        return self.token
    
    def __str__(self):
        return self.name


class User(AbstractUser):
    """
    Custom user model for the shipping platform.
    Users are staff members (carriers or admins) who work for/with companies.
    """
    USER_TYPE_CHOICES = [
        ('carrier', 'Carrier'),
        ('admin', 'Admin'),
    ]
    
    user_type = models.CharField(max_length=20, choices=USER_TYPE_CHOICES, default='admin')
    name = models.CharField(max_length=255, blank=True)
    phone = models.CharField(max_length=20, blank=True)
    
    # Company relationship - users belong to a company (except superusers)
    company = models.ForeignKey(
        Company,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='users',
        help_text='The company this user belongs to. Superusers can access all companies.'
    )
    
    class Meta:
        db_table = 'users'
    
    @property
    def is_carrier(self):
        return self.user_type == 'carrier'
    
    @property
    def is_admin_user(self):
        return self.user_type == 'admin'
    
    @property
    def can_access_all_companies(self):
        """Superusers can access all companies."""
        return self.is_superuser
    
    def can_access_company(self, company):
        """Check if user can access a specific company's data."""
        if self.is_superuser:
            return True
        return self.company_id == company.id
    
    def __str__(self):
        return self.email or self.username

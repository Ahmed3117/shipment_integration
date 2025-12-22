from django.contrib import admin
from django.contrib.auth import get_user_model

from .models import Company

User = get_user_model()


@admin.register(Company)
class CompanyAdmin(admin.ModelAdmin):
    list_display = ['name', 'email', 'is_active', 'created_at']
    search_fields = ['name', 'email']
    list_filter = ['is_active']
    readonly_fields = ['token', 'created_at', 'updated_at']


@admin.register(User)
class UserAdmin(admin.ModelAdmin):
    list_display = ['username', 'email', 'user_type', 'company', 'is_active']
    search_fields = ['username', 'email']
    list_filter = ['user_type', 'is_active']

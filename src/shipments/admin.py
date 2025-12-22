from django.contrib import admin
from .models import Address, ServiceType, Shipment, TrackingEvent, Webhook


@admin.register(Address)
class AddressAdmin(admin.ModelAdmin):
    list_display = ['name', 'city', 'state', 'zip_code', 'country']
    search_fields = ['name', 'city', 'state', 'zip_code']


@admin.register(ServiceType)
class ServiceTypeAdmin(admin.ModelAdmin):
    list_display = ['name', 'code', 'base_rate', 'rate_per_kg', 'estimated_days_min', 'estimated_days_max', 'is_active', 'company']
    list_filter = ['is_active', 'company']


@admin.register(Shipment)
class ShipmentAdmin(admin.ModelAdmin):
    list_display = ['tracking_number', 'company', 'status', 'service_type', 'estimated_cost', 'created_at']
    list_filter = ['status', 'service_type', 'created_at', 'company']
    search_fields = ['tracking_number', 'reference_number']
    readonly_fields = ['tracking_number', 'created_at', 'updated_at']


@admin.register(TrackingEvent)
class TrackingEventAdmin(admin.ModelAdmin):
    list_display = ['shipment', 'status', 'location', 'timestamp']
    list_filter = ['status', 'timestamp']


@admin.register(Webhook)
class WebhookAdmin(admin.ModelAdmin):
    list_display = ['company', 'url', 'is_active', 'created_at']
    list_filter = ['is_active', 'company']

from django.urls import path

from .views import (
    ServiceTypeListView,
    CalculateRatesView,
    ShipmentListCreateView,
    ShipmentDetailView,
    ShipmentCancelView,
    ShipmentLabelView,
    ShipmentStatusUpdateView,
    TrackShipmentView,
    AddressValidationView,
    WebhookListCreateView,
    WebhookDetailView,
)

urlpatterns = [
    # Service Types
    path('services/', ServiceTypeListView.as_view(), name='service-list'),
    
    # Rate Calculation
    path('rates/calculate/', CalculateRatesView.as_view(), name='calculate-rates'),
    
    # Shipments
    path('shipments/', ShipmentListCreateView.as_view(), name='shipment-list-create'),
    path('shipments/<uuid:pk>/', ShipmentDetailView.as_view(), name='shipment-detail'),
    path('shipments/<uuid:pk>/cancel/', ShipmentCancelView.as_view(), name='shipment-cancel'),
    path('shipments/<uuid:pk>/label/', ShipmentLabelView.as_view(), name='shipment-label'),
    path('shipments/<uuid:pk>/status/', ShipmentStatusUpdateView.as_view(), name='shipment-status-update'),
    
    # Tracking
    path('track/<str:tracking_number>/', TrackShipmentView.as_view(), name='track-shipment'),
    
    # Address Validation
    path('address/validate/', AddressValidationView.as_view(), name='address-validate'),
    
    # Webhooks
    path('webhooks/', WebhookListCreateView.as_view(), name='webhook-list-create'),
    path('webhooks/<int:pk>/', WebhookDetailView.as_view(), name='webhook-detail'),
]

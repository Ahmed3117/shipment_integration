from django.urls import path

from .views import (
    ServiceTypeListView,
    AdminServiceTypeListCreateView,
    AdminServiceTypeDetailView,
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
    # Carrier views
    CarrierShipmentListView,
    CarrierShipmentDetailView,
    CarrierStatusUpdateByScanView,
    AssignCarrierView,
)

urlpatterns = [
    # Service Types (Public)
    path('services/', ServiceTypeListView.as_view(), name='service-list'),
    
    # Service Types (Admin CRUD)
    path('admin/services/', AdminServiceTypeListCreateView.as_view(), name='admin-service-list-create'),
    path('admin/services/<int:pk>/', AdminServiceTypeDetailView.as_view(), name='admin-service-detail'),
    
    # Rate Calculation
    path('rates/calculate/', CalculateRatesView.as_view(), name='calculate-rates'),
    
    # Shipments
    path('shipments/', ShipmentListCreateView.as_view(), name='shipment-list-create'),
    path('shipments/<uuid:pk>/', ShipmentDetailView.as_view(), name='shipment-detail'),
    path('shipments/<uuid:pk>/cancel/', ShipmentCancelView.as_view(), name='shipment-cancel'),
    path('shipments/<uuid:pk>/label/', ShipmentLabelView.as_view(), name='shipment-label'),
    path('shipments/<uuid:pk>/status/', ShipmentStatusUpdateView.as_view(), name='shipment-status-update'),
    path('shipments/<uuid:pk>/assign-carrier/', AssignCarrierView.as_view(), name='shipment-assign-carrier'),
    
    # Tracking
    path('track/<str:tracking_number>/', TrackShipmentView.as_view(), name='track-shipment'),
    
    # Address Validation
    path('address/validate/', AddressValidationView.as_view(), name='address-validate'),
    
    # Webhooks
    path('webhooks/', WebhookListCreateView.as_view(), name='webhook-list-create'),
    path('webhooks/<int:pk>/', WebhookDetailView.as_view(), name='webhook-detail'),
    
    # Carrier Endpoints
    path('carrier/shipments/', CarrierShipmentListView.as_view(), name='carrier-shipment-list'),
    path('carrier/shipments/<str:lookup_value>/', CarrierShipmentDetailView.as_view(), name='carrier-shipment-detail'),
    path('carrier/scan/', CarrierStatusUpdateByScanView.as_view(), name='carrier-scan-update'),
]

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
    LabelDownloadView,
    ShipmentStatusUpdateView,
    TrackShipmentView,
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
    path('service-types/', ServiceTypeListView.as_view(), name='service-list'),
    
    # Service Types (Admin CRUD)
    path('admin/service-types/', AdminServiceTypeListCreateView.as_view(), name='admin-service-list-create'),
    path('admin/service-types/<int:pk>/', AdminServiceTypeDetailView.as_view(), name='admin-service-detail'),
    
    # Rate Calculation
    path('rates/calculate/', CalculateRatesView.as_view(), name='calculate-rates'),
    
    # Tracking (Public)
    path('track/<str:tracking_number>/', TrackShipmentView.as_view(), name='track-shipment'),
    
    # Webhooks (Company Token Auth) - MUST be before the catch-all <str:tracking_number>
    path('webhooks/', WebhookListCreateView.as_view(), name='webhook-list-create'),
    path('webhooks/<int:pk>/', WebhookDetailView.as_view(), name='webhook-detail'),
    
    # Carrier Endpoints (JWT Auth) - MUST be before the catch-all <str:tracking_number>
    path('carrier/', CarrierShipmentListView.as_view(), name='carrier-shipment-list'),
    path('carrier/scan/', CarrierStatusUpdateByScanView.as_view(), name='carrier-scan-update'),
    path('carrier/<str:tracking_number>/', CarrierShipmentDetailView.as_view(), name='carrier-shipment-detail'),
    
    # Shipments (Company Token Auth) - catch-all patterns MUST be last
    path('', ShipmentListCreateView.as_view(), name='shipment-list-create'),
    path('<str:tracking_number>/', ShipmentDetailView.as_view(), name='shipment-detail'),
    path('<str:tracking_number>/cancel/', ShipmentCancelView.as_view(), name='shipment-cancel'),
    path('<str:tracking_number>/label/', ShipmentLabelView.as_view(), name='shipment-label'),
    path('<str:shipment_id>/label/download/', LabelDownloadView.as_view(), name='shipment-label-download'),
    path('<str:tracking_number>/status/', ShipmentStatusUpdateView.as_view(), name='shipment-status-update'),
    path('<str:tracking_number>/assign/', AssignCarrierView.as_view(), name='shipment-assign-carrier'),
]

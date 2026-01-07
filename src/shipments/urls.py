from django.urls import path, include

from .views import (
    ServiceTypeListView,
    CalculateRatesView,
    ShipmentListCreateView,
    ShipmentDetailView,
    ShipmentCancelView,
    ShipmentLabelView,
    LabelDownloadView,
    ShipmentStatusUpdateView,
    TrackShipmentView,
    AdminWebhookViewSet,
    # Carrier views
    CarrierShipmentListView,
    CarrierShipmentDetailView,
    CarrierStatusUpdateByScanView,
    CarrierShipmentStatusUpdateView,
    AdminShipmentViewSet,
    AdminServiceTypeViewSet,
    SimpleServiceTypeListView,
    SimpleShipmentListView,
    SimpleWebhookListView,
    SentWebhookListView,
    SentWebhookResendView,
    SentWebhookManualCreateView,
)
from rest_framework.routers import DefaultRouter

router = DefaultRouter()
router.register(r'admin/service-types', AdminServiceTypeViewSet, basename='admin-service-type')
router.register(r'admin/webhooks', AdminWebhookViewSet, basename='admin-webhook')
router.register(r'admin', AdminShipmentViewSet, basename='admin-shipment')

urlpatterns = [
    # Service Types (Public)
    path('service-types/', ServiceTypeListView.as_view(), name='service-list'),
    
    # Shipments (Company Token Auth)
    path('', ShipmentListCreateView.as_view(), name='shipment-list-create'),
    
    # Sent Webhooks (Company Token Auth)
    path('webhooks/sent/', SentWebhookListView.as_view(), name='sent-webhook-list'),
    path('webhooks/sent/<int:pk>/resend/', SentWebhookResendView.as_view(), name='sent-webhook-resend'),
    path('webhooks/sent/manual/', SentWebhookManualCreateView.as_view(), name='sent-webhook-manual-trigger'),
    
    # Admin CRUD via Routers
    path('', include(router.urls)),
    
    # Rate Calculation
    path('rates/calculate/', CalculateRatesView.as_view(), name='calculate-rates'),
    
    # Tracking (Public)
    path('track/<str:tracking_number>/', TrackShipmentView.as_view(), name='track-shipment'),
    
    # Webhooks (moved to Admin CRUD)
    
    # Carrier Endpoints (JWT Auth) - MUST be before the catch-all <str:tracking_number>
    path('carrier/', CarrierShipmentListView.as_view(), name='carrier-shipment-list'),
    path('carrier/<str:tracking_number>/scan/', CarrierStatusUpdateByScanView.as_view(), name='carrier-scan-pickup'),
    path('carrier/<str:tracking_number>/', CarrierShipmentDetailView.as_view(), name='carrier-shipment-detail'),
    path('carrier/<str:tracking_number>/status/', CarrierShipmentStatusUpdateView.as_view(), name='carrier-status-update'),
    
    # Shipments

    path('<str:tracking_number>/', ShipmentDetailView.as_view(), name='shipment-detail'),
    path('<str:tracking_number>/cancel/', ShipmentCancelView.as_view(), name='shipment-cancel'),
    path('<str:tracking_number>/label/', ShipmentLabelView.as_view(), name='shipment-label'),
    path('<str:shipment_id>/label/download/', LabelDownloadView.as_view(), name='shipment-label-download'),
    path('<str:tracking_number>/status/', ShipmentStatusUpdateView.as_view(), name='shipment-status-update'),

    # ─────────────────────────────────────────────────────────────────
    # SIMPLE LIST ENDPOINTS (Selects/Dropdowns)
    # ─────────────────────────────────────────────────────────────────
    path('simple/service-types/', SimpleServiceTypeListView.as_view(), name='simple-service-type-list'),
    path('simple/shipments/', SimpleShipmentListView.as_view(), name='simple-shipment-list'),
    path('simple/webhooks/', SimpleWebhookListView.as_view(), name='simple-webhook-list'),
]

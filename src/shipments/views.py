from datetime import date, timedelta
from django.db import models
from rest_framework import generics, status
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.permissions import AllowAny
from django.shortcuts import get_object_or_404

from .models import ServiceType, Shipment, TrackingEvent, Webhook
from .serializers import (
    ServiceTypeSerializer,
    ServiceTypeAdminSerializer,
    RateCalculationRequestSerializer,
    RateOptionSerializer,
    ShipmentCreateSerializer,
    ShipmentListSerializer,
    ShipmentDetailSerializer,
    TrackingEventSerializer,
    TrackingResponseSerializer,
    WebhookSerializer,
    AddressValidationSerializer,
    AddressValidationResponseSerializer,
    ShipmentStatusUpdateSerializer,
    CarrierShipmentListSerializer,
    CarrierStatusUpdateSerializer,
    AssignCarrierSerializer,
)
from .services import update_shipment_status, send_webhook_notification
from .permissions import IsAdmin, IsCarrier, IsCarrierOrAdmin


# --- Service Types (Public) ---
class ServiceTypeListView(generics.ListAPIView):
    """List all active shipping service types (public endpoint)."""
    queryset = ServiceType.objects.filter(is_active=True)
    serializer_class = ServiceTypeSerializer
    permission_classes = [AllowAny]


# --- Service Types (Admin CRUD) ---
class AdminServiceTypeListCreateView(generics.ListCreateAPIView):
    """
    Admin endpoint to list all service types (including inactive) and create new ones.
    
    GET: List all service types
    POST: Create a new service type
    """
    queryset = ServiceType.objects.all()
    serializer_class = ServiceTypeAdminSerializer
    permission_classes = [IsAdmin]
    
    def get_queryset(self):
        queryset = ServiceType.objects.all()
        # Optional filter by is_active
        is_active = self.request.query_params.get('is_active')
        if is_active is not None:
            queryset = queryset.filter(is_active=is_active.lower() == 'true')
        return queryset.order_by('name')


class AdminServiceTypeDetailView(generics.RetrieveUpdateDestroyAPIView):
    """
    Admin endpoint to get, update, or delete a service type.
    
    GET: Get service type details
    PUT/PATCH: Update service type
    DELETE: Delete service type (only if not used in any shipment)
    """
    queryset = ServiceType.objects.all()
    serializer_class = ServiceTypeAdminSerializer
    permission_classes = [IsAdmin]
    
    def destroy(self, request, *args, **kwargs):
        instance = self.get_object()
        # Check if service type is in use
        shipment_count = Shipment.objects.filter(service_type=instance).count()
        if shipment_count > 0:
            return Response(
                {
                    'error': f'Cannot delete service type. It is used in {shipment_count} shipment(s).',
                    'suggestion': 'Consider deactivating it instead by setting is_active to false.'
                },
                status=status.HTTP_400_BAD_REQUEST
            )
        return super().destroy(request, *args, **kwargs)


# --- Rate Calculation ---
class CalculateRatesView(generics.GenericAPIView):
    """Calculate shipping rates based on origin, destination, and package details."""
    serializer_class = RateCalculationRequestSerializer
    
    def post(self, request):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        data = serializer.validated_data
        weight = data['weight']
        
        services = ServiceType.objects.filter(is_active=True)
        rates = []
        
        for service in services:
            estimated_cost = service.base_rate + (service.rate_per_kg * weight)
            
            rates.append({
                'service_id': service.id,
                'service_name': service.name,
                'service_code': service.code,
                'estimated_cost': round(estimated_cost, 2),
                'estimated_delivery_date_min': date.today() + timedelta(days=service.estimated_days_min),
                'estimated_delivery_date_max': date.today() + timedelta(days=service.estimated_days_max),
            })
        
        return Response({
            'origin': {
                'city': data['origin_city'],
                'state': data['origin_state'],
                'zip_code': data['origin_zip_code'],
                'country': data['origin_country'],
            },
            'destination': {
                'city': data['destination_city'],
                'state': data['destination_state'],
                'zip_code': data['destination_zip_code'],
                'country': data['destination_country'],
            },
            'package': {
                'weight': data['weight'],
                'length': data['length'],
                'width': data['width'],
                'height': data['height'],
            },
            'rates': RateOptionSerializer(rates, many=True).data
        })


# --- Shipment CRUD ---
class ShipmentListCreateView(generics.ListCreateAPIView):
    """List shipments or create a new shipment."""
    
    def get_serializer_class(self):
        if self.request.method == 'POST':
            return ShipmentCreateSerializer
        return ShipmentListSerializer
    
    def get_queryset(self):
        queryset = Shipment.objects.filter(user=self.request.user)
        
        # Filter by date range
        start_date = self.request.query_params.get('start_date')
        end_date = self.request.query_params.get('end_date')
        status_filter = self.request.query_params.get('status')
        
        if start_date:
            queryset = queryset.filter(created_at__date__gte=start_date)
        if end_date:
            queryset = queryset.filter(created_at__date__lte=end_date)
        if status_filter:
            queryset = queryset.filter(status=status_filter)
        
        return queryset
    
    def perform_create(self, serializer):
        serializer.save(user=self.request.user)
    
    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        shipment = serializer.save(user=request.user)
        
        response_serializer = ShipmentDetailSerializer(shipment)
        return Response({
            'message': 'Shipment created successfully.',
            'shipment': response_serializer.data
        }, status=status.HTTP_201_CREATED)


class ShipmentDetailView(generics.RetrieveAPIView):
    """Retrieve shipment details by ID."""
    serializer_class = ShipmentDetailSerializer
    lookup_field = 'pk'
    
    def get_queryset(self):
        return Shipment.objects.filter(user=self.request.user)


class ShipmentCancelView(generics.GenericAPIView):
    """Cancel a shipment."""
    serializer_class = ShipmentDetailSerializer
    
    def post(self, request, pk):
        shipment = get_object_or_404(Shipment, pk=pk, user=request.user)
        
        if shipment.status in ['delivered', 'cancelled']:
            return Response({
                'error': f'Cannot cancel shipment with status: {shipment.status}'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        if shipment.status in ['picked_up', 'in_transit', 'out_for_delivery']:
            return Response({
                'error': 'Cannot cancel shipment that is already in transit. Please contact support.'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        shipment.status = 'cancelled'
        shipment.save()
        
        TrackingEvent.objects.create(
            shipment=shipment,
            status='cancelled',
            description='Shipment cancelled by user.',
            location=None
        )
        
        return Response({
            'message': 'Shipment cancelled successfully.',
            'shipment_id': str(shipment.id),
            'tracking_number': shipment.tracking_number,
            'refund_status': 'Refund will be processed within 3-5 business days.' if shipment.estimated_cost > 0 else 'No refund applicable.'
        })


# --- Label ---
class ShipmentLabelView(generics.GenericAPIView):
    """Get shipping label for a shipment."""
    
    def get(self, request, pk):
        shipment = get_object_or_404(Shipment, pk=pk, user=request.user)
        
        if shipment.status == 'cancelled':
            return Response({
                'error': 'Cannot generate label for cancelled shipment.'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        # In a real implementation, this would generate or fetch the actual label
        label_data = {
            'shipment_id': str(shipment.id),
            'tracking_number': shipment.tracking_number,
            'label_format': 'PDF',
            'label_url': f'/api/shipments/{shipment.id}/label/download/',
            'label_zpl': None,  # Would contain ZPL data if requested
        }
        
        return Response(label_data)


# --- Tracking ---
class TrackShipmentView(generics.GenericAPIView):
    """Track a shipment by tracking number."""
    permission_classes = [AllowAny]  # Allow public tracking
    
    def get(self, request, tracking_number):
        shipment = get_object_or_404(Shipment, tracking_number=tracking_number)
        
        events = shipment.tracking_events.all()
        last_event = events.first() if events.exists() else None
        
        response_data = {
            'tracking_number': shipment.tracking_number,
            'current_status': shipment.status,
            'last_update': last_event.timestamp if last_event else shipment.updated_at,
            'reference_number': shipment.reference_number,
            'estimated_delivery_date': shipment.estimated_delivery_date,
            'history': TrackingEventSerializer(events, many=True).data
        }
        
        return Response(response_data)


# --- Address Validation ---
class AddressValidationView(generics.GenericAPIView):
    """Validate a shipping address."""
    serializer_class = AddressValidationSerializer
    
    def post(self, request):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        data = serializer.validated_data
        
        # Simple validation logic (in real implementation, integrate with address validation service)
        is_valid = True
        message = 'Address is valid.'
        
        # Check zip code format
        zip_code = data['zip_code']
        if not zip_code or len(zip_code) < 3:
            is_valid = False
            message = 'Zip code not found.'
        
        # Check city/state
        if not data['city'] or not data['state']:
            is_valid = False
            message = 'City and state are required.'
        
        response_data = {
            'is_valid': is_valid,
            'message': message,
            'suggested_address': data if is_valid else None
        }
        
        return Response(response_data)


# --- Webhooks ---
class WebhookListCreateView(generics.ListCreateAPIView):
    """List or create webhooks."""
    serializer_class = WebhookSerializer
    
    def get_queryset(self):
        return Webhook.objects.filter(user=self.request.user)
    
    def perform_create(self, serializer):
        import secrets
        secret = secrets.token_urlsafe(32)
        serializer.save(user=self.request.user, secret=secret)
    
    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        webhook = self.perform_create(serializer)
        
        return Response({
            'message': 'Webhook registered successfully.',
            'webhook': serializer.data
        }, status=status.HTTP_201_CREATED)


class WebhookDetailView(generics.RetrieveUpdateDestroyAPIView):
    """Retrieve, update, or delete a webhook."""
    serializer_class = WebhookSerializer
    lookup_field = 'pk'
    
    def get_queryset(self):
        return Webhook.objects.filter(user=self.request.user)
    
    def destroy(self, request, *args, **kwargs):
        instance = self.get_object()
        self.perform_destroy(instance)
        return Response({
            'message': 'Webhook deleted successfully.'
        }, status=status.HTTP_200_OK)


# --- Shipment Status Update (for carrier/admin) ---
class ShipmentStatusUpdateView(generics.GenericAPIView):
    """
    Update shipment status and trigger webhooks.
    This endpoint would typically be used by carriers or admin.
    """
    serializer_class = ShipmentStatusUpdateSerializer
    
    def post(self, request, pk):
        shipment = get_object_or_404(Shipment, pk=pk, user=request.user)
        
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        new_status = serializer.validated_data['status']
        description = serializer.validated_data.get('description', '')
        location = serializer.validated_data.get('location', '')
        
        # Validate status transition
        if shipment.status == 'cancelled':
            return Response({
                'error': 'Cannot update status of a cancelled shipment.'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        if shipment.status == 'delivered' and new_status != 'returned':
            return Response({
                'error': 'Delivered shipment can only be changed to returned.'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        # Update status and send webhooks
        update_shipment_status(
            shipment=shipment,
            new_status=new_status,
            description=description,
            location=location
        )
        
        return Response({
            'message': f'Shipment status updated to {new_status}.',
            'shipment_id': str(shipment.id),
            'tracking_number': shipment.tracking_number,
            'new_status': new_status,
            'webhook_triggered': True
        })


# --- Carrier Views ---
class CarrierShipmentListView(generics.ListAPIView):
    """
    List all shipments assigned to the carrier.
    Carriers can filter by status and date range.
    """
    serializer_class = CarrierShipmentListSerializer
    permission_classes = [IsCarrier]
    
    def get_queryset(self):
        queryset = Shipment.objects.filter(carrier=self.request.user)
        
        # Filter by status
        status_filter = self.request.query_params.get('status')
        if status_filter:
            queryset = queryset.filter(status=status_filter)
        
        # Filter by date range
        start_date = self.request.query_params.get('start_date')
        end_date = self.request.query_params.get('end_date')
        if start_date:
            queryset = queryset.filter(created_at__date__gte=start_date)
        if end_date:
            queryset = queryset.filter(created_at__date__lte=end_date)
        
        return queryset.order_by('-created_at')


class CarrierShipmentDetailView(generics.RetrieveAPIView):
    """
    Retrieve shipment details for carrier.
    Allows lookup by pk, tracking_number, or reference_number.
    """
    serializer_class = ShipmentDetailSerializer
    permission_classes = [IsCarrier]
    
    def get_object(self):
        # Support lookup by pk, tracking_number, or reference_number
        lookup_value = self.kwargs.get('lookup_value')
        
        # Try by UUID first
        try:
            import uuid
            uuid.UUID(lookup_value)
            return get_object_or_404(Shipment, pk=lookup_value, carrier=self.request.user)
        except (ValueError, AttributeError):
            pass
        
        # Try by tracking_number or reference_number
        shipment = Shipment.objects.filter(
            carrier=self.request.user
        ).filter(
            models.Q(tracking_number=lookup_value) | models.Q(reference_number=lookup_value)
        ).first()
        
        if not shipment:
            from django.http import Http404
            raise Http404("Shipment not found.")
        
        return shipment


class CarrierStatusUpdateByScanView(generics.GenericAPIView):
    """
    Update shipment status by scanning reference_number or tracking_number.
    This is the primary endpoint for carriers to update status via mobile scanning.
    """
    serializer_class = CarrierStatusUpdateSerializer
    permission_classes = [IsCarrier]
    
    def post(self, request):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        data = serializer.validated_data
        reference_number = data.get('reference_number')
        tracking_number = data.get('tracking_number')
        new_status = data['status']
        description = data.get('description', '')
        location = data.get('location', '')
        
        # Find shipment by reference_number or tracking_number
        shipment = None
        if reference_number:
            shipment = Shipment.objects.filter(
                reference_number=reference_number,
                carrier=request.user
            ).first()
        elif tracking_number:
            shipment = Shipment.objects.filter(
                tracking_number=tracking_number,
                carrier=request.user
            ).first()
        
        if not shipment:
            return Response({
                'error': 'Shipment not found or not assigned to you.'
            }, status=status.HTTP_404_NOT_FOUND)
        
        # Validate status transition
        if shipment.status == 'cancelled':
            return Response({
                'error': 'Cannot update status of a cancelled shipment.'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        if shipment.status == 'delivered' and new_status != 'returned':
            return Response({
                'error': 'Delivered shipment can only be changed to returned.'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        # Update status and send webhooks, recording the carrier who made the update
        update_shipment_status(
            shipment=shipment,
            new_status=new_status,
            description=description,
            location=location,
            created_by=request.user
        )
        
        return Response({
            'message': f'Shipment status updated to {new_status}.',
            'shipment_id': str(shipment.id),
            'tracking_number': shipment.tracking_number,
            'reference_number': shipment.reference_number,
            'new_status': new_status,
            'updated_by': request.user.email
        })


class AssignCarrierView(generics.GenericAPIView):
    """
    Assign a carrier to a shipment. Only admin users can assign carriers.
    """
    serializer_class = AssignCarrierSerializer
    
    def post(self, request, pk):
        # Check if user is admin
        if not request.user.is_staff and request.user.user_type != 'admin':
            return Response({
                'error': 'Only admin users can assign carriers.'
            }, status=status.HTTP_403_FORBIDDEN)
        
        shipment = get_object_or_404(Shipment, pk=pk)
        
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        carrier_id = serializer.validated_data['carrier_id']
        
        from accounts.models import User
        carrier = get_object_or_404(User, pk=carrier_id)
        
        if not carrier.is_carrier:
            return Response({
                'error': 'The specified user is not a carrier.'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        shipment.carrier = carrier
        shipment.save()
        
        return Response({
            'message': 'Carrier assigned successfully.',
            'shipment_id': str(shipment.id),
            'tracking_number': shipment.tracking_number,
            'carrier_id': str(carrier.id),
            'carrier_email': carrier.email
        })

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
    WebhookCreateSerializer,
    WebhookDetailSerializer,
    ShipmentStatusUpdateSerializer,
    CarrierShipmentListSerializer,
    CarrierStatusUpdateSerializer,
    AssignCarrierSerializer,
)
from .services import update_shipment_status, send_webhook_notification
from .permissions import IsAdmin, IsCarrier, IsCarrierOrAdmin, IsCompany, IsCompanyOrAdmin
from accounts.authentication import CompanyUser


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
    """
    List shipments or create a new shipment.
    Requires Company token authentication.
    """
    permission_classes = [AllowAny]

    def get_serializer_class(self):
        if self.request.method == 'POST':
            return ShipmentCreateSerializer
        return ShipmentListSerializer

    def get_queryset(self):
        user = self.request.user
        if not user or not user.is_authenticated:
            return Shipment.objects.none()

        queryset = Shipment.objects.all()
        # If Company token auth
        if isinstance(user, CompanyUser):
            return queryset.filter(company=user.company).order_by('-created_at')

        # If superuser, they can see everything
        if user.is_superuser:
            return queryset.order_by('-created_at')

        # Regular Admin/Staff
        if hasattr(user, 'company') and user.company:
            queryset = queryset.filter(company=user.company)
        else:
            # User has no company and is not superuser
            return Shipment.objects.none()

        return queryset.order_by('-created_at')

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

        return queryset.order_by('-created_at')

    def perform_create(self, serializer):
        user = self.request.user
        from accounts.authentication import CompanyUser
        company = None
        if isinstance(user, CompanyUser):
            company = user.company
        elif user.is_superuser:
            company = serializer.validated_data.get('company', None)
            if not company:
                raise serializers.ValidationError({'company': 'Company is required for superuser shipment creation.'})
        elif hasattr(user, 'company') and user.company:
            company = user.company
        else:
            raise serializers.ValidationError({'company': 'Company is required for shipment creation.'})
        serializer.save(company=company)

    def create(self, request, *args, **kwargs):
        user = request.user
        company = None
        
        # 1. ALWAYS prioritize detecting company from CompanyTokenAuthentication first
        if user and user.is_authenticated and isinstance(user, CompanyUser):
            company = user.company
        
        # 2. If not a CompanyUser, check if they are a regular user with a company or a superuser
        if not company and user and user.is_authenticated:
            if user.is_superuser:
                # Superuser can specify company in data explicitly
                company_id = request.data.get('company_id') or request.data.get('company')
                if company_id:
                    from accounts.models import Company
                    try:
                        if str(company_id).isdigit():
                            company = Company.objects.get(id=company_id)
                        else:
                            company = Company.objects.get(name=company_id)
                    except (Company.DoesNotExist, ValueError):
                        pass
            elif hasattr(user, 'company') and user.company:
                # Regular admin/carrier belonging to a company
                company = user.company

        # 3. If no company detected yet, explicitly require it
        if not company:
            return Response(
                {'error': 'A valid company token (X-Company-Token) or company identification is required.'}, 
                status=status.HTTP_401_UNAUTHORIZED
            )

        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        reference_number = serializer.validated_data.get('reference_number')
        existing = None
        if reference_number and company:
            existing = Shipment.objects.filter(reference_number=reference_number, company=company).first()
        if existing:
            response_serializer = ShipmentDetailSerializer(existing)
            return Response({
                'message': 'Shipment with this reference_number already exists.',
                'shipment': response_serializer.data
            }, status=status.HTTP_200_OK)

        shipment = serializer.save(company=company)
        response_serializer = ShipmentDetailSerializer(shipment)
        return Response({
            'message': 'Shipment created successfully.',
            'shipment': response_serializer.data
        }, status=status.HTTP_201_CREATED)


class ShipmentDetailView(generics.RetrieveUpdateDestroyAPIView):
    """Retrieve, update, or delete shipment details by tracking number."""
    serializer_class = ShipmentDetailSerializer
    permission_classes = [IsAdmin]
    lookup_field = 'tracking_number'
    lookup_url_kwarg = 'tracking_number'

    def get_queryset(self):
        user = self.request.user
        if not user or not user.is_authenticated:
            return Shipment.objects.none()

        queryset = Shipment.objects.all()
        if user.is_superuser:
            return queryset

        if isinstance(user, CompanyUser):
            queryset = queryset.filter(company=user.company)
        elif hasattr(user, 'company') and user.company:
            queryset = queryset.filter(company=user.company)
        else:
            return Shipment.objects.none()

        return queryset

    def destroy(self, request, *args, **kwargs):
        instance = self.get_object()
        if instance.status not in ['pending', 'cancelled']:
            return Response(
                {'error': 'Can only delete pending or cancelled shipments.'},
                status=status.HTTP_400_BAD_REQUEST
            )
        self.perform_destroy(instance)
        return Response(status=status.HTTP_204_NO_CONTENT)


class ShipmentCancelView(generics.GenericAPIView):
    """Cancel a shipment."""
    serializer_class = ShipmentDetailSerializer
    permission_classes = [IsCompany]
    
    def post(self, request, tracking_number):
        company = request.user.company
        shipment = get_object_or_404(Shipment, tracking_number=tracking_number, company=company)
        
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
    permission_classes = [IsCompany]
    
    def get(self, request, tracking_number):
        company = request.user.company
        shipment = get_object_or_404(Shipment, tracking_number=tracking_number, company=company)
        
        if shipment.status == 'cancelled':
            return Response({
                'error': 'Cannot generate label for cancelled shipment.'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        # In a real implementation, this would generate or fetch the actual label
        shipment_serializer = ShipmentDetailSerializer(shipment)
        
        label_data = {
            'shipment': shipment_serializer.data,
            'label_info': {
                'label_format': 'PDF',
                'label_url': f'/api/shipments/{shipment.id}/label/download/',
                'label_zpl': None,
            }
        }
        
        return Response(label_data)


class LabelDownloadView(generics.GenericAPIView):
    """View to download the shipping label PDF."""
    permission_classes = [AllowAny] # Allow public download if tracking number/ID is known
    
    def get(self, request, shipment_id):
        # In a real app, this would return an actual PDF file
        # Here we mock it with a simple text response or a redirect
        from django.http import HttpResponse
        
        # Check if shipment_id is a UUID (from the label_url) or a tracking_number
        if len(str(shipment_id)) > 20: # Likely a UUID
            shipment = get_object_or_404(Shipment, id=shipment_id)
        else:
            shipment = get_object_or_404(Shipment, tracking_number=shipment_id)
            
        # Minimal valid PDF structure
        pdf_content = (
            b"%PDF-1.1\n"
            b"1 0 obj << /Type /Catalog /Pages 2 0 R >> endobj\n"
            b"2 0 obj << /Type /Pages /Kids [3 0 R] /Count 1 >> endobj\n"
            b"3 0 obj << /Type /Page /Parent 2 0 R /Resources << >> /Contents 4 0 R >> endobj\n"
            b"4 0 obj << /Length 51 >> stream\n"
            b"BT /F1 24 Tf 100 700 Td (Shipment Label: " + shipment.tracking_number.encode() + b") Tj ET\n"
            b"endstream endobj\n"
            b"xref\n0 5\n0000000000 65535 f \n0000000009 00000 n \n0000000056 00000 n \n0000000111 00000 n \n0000000183 00000 n \ntrailer << /Size 5 /Root 1 0 R >>\nstartxref\n284\n%%EOF"
        )
            
        response = HttpResponse(pdf_content, content_type='application/pdf')
        response['Content-Disposition'] = f'attachment; filename="label_{shipment.tracking_number}.pdf"'
        return response


# --- Tracking ---
class TrackShipmentView(generics.GenericAPIView):
    """Track a shipment by tracking number."""
    permission_classes = [AllowAny]  # Allow public tracking

    def get(self, request, tracking_number):
        # Anyone can track a shipment by tracking number, no authentication required
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


# --- Webhooks ---
class WebhookListCreateView(generics.ListCreateAPIView):
    """List or create webhooks."""
    permission_classes = [IsCompany]
    
    def get_serializer_class(self):
        if self.request.method == 'POST':
            return WebhookCreateSerializer
        return WebhookSerializer
    
    def get_queryset(self):
        company = self.request.user.company
        return Webhook.objects.filter(company=company)
    
    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        import secrets
        company = request.user.company
        secret = secrets.token_urlsafe(32)
        webhook = serializer.save(company=company, secret=secret)
        
        return Response({
            'message': 'Webhook registered successfully.',
            'webhook': WebhookDetailSerializer(webhook).data
        }, status=status.HTTP_201_CREATED)


class WebhookDetailView(generics.RetrieveUpdateDestroyAPIView):
    """Retrieve, update, or delete a webhook."""
    serializer_class = WebhookSerializer
    permission_classes = [IsCompany]
    lookup_field = 'pk'
    
    def get_queryset(self):
        company = self.request.user.company
        return Webhook.objects.filter(company=company)
    
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
    This endpoint is used by carriers or admin.
    """
    serializer_class = ShipmentStatusUpdateSerializer
    permission_classes = [IsCarrierOrAdmin]
    
    def post(self, request, tracking_number):
        shipment = get_object_or_404(Shipment, tracking_number=tracking_number)
        
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
            location=location,
            created_by=request.user
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
    Allows lookup by tracking_number.
    """
    serializer_class = ShipmentDetailSerializer
    permission_classes = [IsCarrier]
    
    def get_object(self):
        tracking_number = self.kwargs.get('tracking_number')
        return get_object_or_404(Shipment, tracking_number=tracking_number, carrier=self.request.user)


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
    permission_classes = [IsAdmin]
    
    def post(self, request, tracking_number):
        shipment = get_object_or_404(Shipment, tracking_number=tracking_number)
        
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

from datetime import date, timedelta
from django.db import models
from rest_framework import generics, status, viewsets
from rest_framework.decorators import action
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
    BulkAssignCarrierSerializer,
    SimpleServiceTypeSerializer,
    SimpleShipmentSerializer,
    SimpleWebhookSerializer,
)
from .services import update_shipment_status, send_webhook_notification
from .permissions import IsAdmin, IsCarrier, IsCarrierOrAdmin, IsCompany, IsCompanyOrAdmin
from accounts.authentication import CompanyUser
from rest_framework import filters
from django_filters.rest_framework import DjangoFilterBackend


# --- Service Types (Public) ---
class ServiceTypeListView(generics.ListAPIView):
    """
    List active shipping service types for the authenticated company.
    """
    serializer_class = ServiceTypeSerializer
    permission_classes = [IsCompany]
    
    def get_queryset(self):
        # Strict filtering: only return services for the authenticated company
        return ServiceType.objects.filter(
            is_active=True,
            company=self.request.user.company
        ).order_by('name')


# --- Service Types (Admin CRUD) ---
class AdminServiceTypeViewSet(viewsets.ModelViewSet):
    """
    Admin ViewSet for full CRUD on service types.
    Superuser: Full access.
    Admin: Access only to their company's service types.
    """
    serializer_class = ServiceTypeAdminSerializer
    permission_classes = [IsAdmin]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter]
    filterset_fields = ['company', 'is_active']
    search_fields = ['name', 'code', 'company__name']
    
    def get_queryset(self):
        user = self.request.user
        queryset = ServiceType.objects.all()
        
        if not user.is_superuser:
            if hasattr(user, 'company') and user.company:
                queryset = queryset.filter(company=user.company)
            else:
                return ServiceType.objects.none()
        
        # Optional filter by is_active
        is_active = self.request.query_params.get('is_active')
        if is_active is not None:
            queryset = queryset.filter(is_active=is_active.lower() == 'true')
            
        return queryset.order_by('name')

    def destroy(self, request, *args, **kwargs):
        instance = self.get_object()
        # Check if service type is in use
        shipment_count = Shipment.objects.filter(service_type=instance).count()
        if shipment_count > 0:
            return Response(
                {
                    'error': f'لا يمكن حذف نوع الخدمة. يتم استخدامها في {shipment_count} شحنة (شحنات).',
                    'suggestion': 'فكر في إلغاء تنشيطه بدلاً من ذلك عن طريق تعيين is_active إلى false.'
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
        
        # Determine company to filter services
        user = request.user
        from accounts.authentication import CompanyUser
        company = None
        if isinstance(user, CompanyUser):
            company = user.company
        elif user.is_authenticated and not user.is_superuser:
            company = getattr(user, 'company', None)
        
        services = ServiceType.objects.filter(is_active=True)
        if company:
            services = services.filter(company=company)
        elif not user.is_superuser:
            # If not superuser and no company found, no services available
            return Response({'error': 'لا توجد خدمات متاحة لحسابك.'}, status=status.HTTP_403_FORBIDDEN)
            
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
            queryset = queryset.filter(company=user.company)
        elif user.is_superuser:
            pass # Superuser sees all
        elif hasattr(user, 'company') and user.company:
            queryset = queryset.filter(company=user.company)
        else:
            return Shipment.objects.none()

        # Filter by query params
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
                {'error': 'مطلوب رمز شركة صالح (X-Company-Token) أو تحديد هوية الشركة.'}, 
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
                'message': 'شحنة بنفس الرقم المرجعي موجودة بالفعل.',
                'shipment': response_serializer.data
            }, status=status.HTTP_200_OK)

        shipment = serializer.save(company=company)
        response_serializer = ShipmentDetailSerializer(shipment)
        return Response({
            'message': 'تم إنشاء الشحنة بنجاح.',
            'shipment': response_serializer.data
        }, status=status.HTTP_201_CREATED)


class ShipmentDetailView(generics.RetrieveUpdateDestroyAPIView):
    """Retrieve, update, or delete shipment details by tracking number."""
    serializer_class = ShipmentDetailSerializer
    permission_classes = [IsCompanyOrAdmin]
    lookup_field = 'tracking_number'
    lookup_url_kwarg = 'tracking_number'

    def get_queryset(self):
        user = self.request.user
        if not user or not user.is_authenticated:
            return Shipment.objects.none()

        # For the queryset, we return all shipments if superuser,
        # otherwise we return shipments for the specific company to ensure 404/403 logic works.
        queryset = Shipment.objects.all()
        if user.is_superuser:
            return queryset

        # We return the full queryset here but check ownership in get_object 
        # to provide the specific required error message.
        return queryset

    def get_object(self):
        queryset = self.filter_queryset(self.get_queryset())
        
        # Perform the lookup
        lookup_url_kwarg = self.lookup_url_kwarg or self.lookup_field
        filter_kwargs = {self.lookup_field: self.kwargs[lookup_url_kwarg]}
        
        # First check if the shipment exists at all
        shipment = Shipment.objects.filter(**filter_kwargs).first()
        
        if not shipment:
            from django.http import Http404
            raise Http404

        # Check company ownership
        user = self.request.user
        
        # Superuser can see everything
        if user.is_superuser:
            return shipment

        # Get the user's company
        user_company = None
        if isinstance(user, CompanyUser):
            user_company = user.company
        elif hasattr(user, 'company'):
            user_company = user.company

        # If User has a company, check if it matches the shipment's company
        if user_company and shipment.company != user_company:
            from rest_framework.exceptions import PermissionDenied
            raise PermissionDenied({'error': 'هذه الشحنة غير تابعة لهذة الشركة'})
            
        return shipment

    def destroy(self, request, *args, **kwargs):
        instance = self.get_object()
        if instance.status not in ['pending', 'cancelled']:
            return Response(
                {'error': 'يمكن حذف الشحنات المعلقة أو الملغاة فقط.'},
                status=status.HTTP_400_BAD_REQUEST
            )
        self.perform_destroy(instance)
        return Response(status=status.HTTP_204_NO_CONTENT)


class ShipmentCancelView(generics.GenericAPIView):
    """Cancel a shipment."""
    serializer_class = ShipmentDetailSerializer
    permission_classes = [IsCompany]
    
    def post(self, request, tracking_number):
        user = request.user
        # Standard lookup
        shipment = Shipment.objects.filter(tracking_number=tracking_number).first()
        if not shipment:
            from django.http import Http404
            raise Http404
            
        # Ownership check
        user_company = getattr(user, 'company', None)
        if hasattr(user, 'company_id') and user.company_id:
             user_company = user.company

        if not user.is_superuser and shipment.company != user_company:
            return Response({'error': 'هذه الشحنة غير تابعة لهذة الشركة'}, status=status.HTTP_403_FORBIDDEN)
        
        if shipment.status in ['delivered', 'cancelled']:
            return Response({
                'error': f'لا يمكن إلغاء الشحنة بالحالة: {shipment.status}'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        if shipment.status in ['picked_up', 'in_transit', 'out_for_delivery']:
            return Response({
                'error': 'لا يمكن إلغاء شحنة قيد النقل بالفعل. يرجى الاتصال بالدعم.'
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
            'message': 'تم إلغاء الشحنة بنجاح.',
            'shipment_id': str(shipment.id),
            'tracking_number': shipment.tracking_number,
            'is_paid': shipment.is_paid,
            'status': shipment.status
        })


# --- Label ---
class ShipmentLabelView(generics.GenericAPIView):
    """Get shipping label for a shipment."""
    permission_classes = [IsCompany]
    
    def get(self, request, tracking_number):
        user = request.user
        # Standard lookup
        shipment = Shipment.objects.filter(tracking_number=tracking_number).first()
        if not shipment:
            from django.http import Http404
            raise Http404

        # Ownership check
        user_company = getattr(user, 'company', None)
        if not user.is_superuser and shipment.company != user_company:
            return Response({'error': 'هذه الشحنة غير تابعة لهذة الشركة'}, status=status.HTTP_403_FORBIDDEN)
        
        if shipment.status == 'cancelled':
            return Response({
                'error': 'لا يمكن إنشاء ملصق لشحنة ملغاة.'
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
        
        # Check if shipment_id is a numeric ID or a tracking_number
        if str(shipment_id).isdigit() and len(str(shipment_id)) < 11:
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


# --- Webhooks (Admin CRUD) ---
class AdminWebhookViewSet(viewsets.ModelViewSet):
    """
    CRUD for webhooks, accessible by admins and superusers.
    Admins can only see and manage webhooks for their own company.
    """
    permission_classes = [IsAdmin]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter]
    filterset_fields = ['company', 'is_active']
    search_fields = ['company__name', 'company__phone', 'url', 'secret']
    lookup_field = 'pk'
    
    def get_serializer_class(self):
        if self.action == 'create':
            return WebhookCreateSerializer
        elif self.request.method in ['GET'] and self.detail:
            return WebhookDetailSerializer
        return WebhookSerializer

    def get_queryset(self):
        user = self.request.user
        if user.is_superuser:
            return Webhook.objects.all()
        return Webhook.objects.filter(company=user.company)

    def perform_create(self, serializer):
        import secrets
        user = self.request.user
        
        # Determine company
        if user.is_superuser:
            company_id = self.request.data.get('company_id')
            if not company_id:
                from rest_framework.exceptions import ValidationError
                raise ValidationError({'company_id': 'مطلوب معرف الشركة للمشرفين المتميزين.'})
            from accounts.models import Company
            try:
                company = Company.objects.get(id=company_id)
            except Company.DoesNotExist:
                from rest_framework.exceptions import ValidationError
                raise ValidationError({'company_id': 'معرف الشركة غير صالح.'})
        else:
            company = user.company
            
        secret = secrets.token_urlsafe(32)
        serializer.save(company=company, secret=secret)

    def create(self, request, *args, **kwargs):
        response = super().create(request, *args, **kwargs)
        # Wrap response data for consistency (optional but following existing style)
        return Response({
            'message': 'تم تسجيل الويب هوك بنجاح.',
            'webhook': response.data
        }, status=status.HTTP_201_CREATED)

    def destroy(self, request, *args, **kwargs):
        instance = self.get_object()
        self.perform_destroy(instance)
        return Response({
            'message': 'تم حذف الويب هوك بنجاح.'
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
                'error': 'لا يمكن تحديث حالة شحنة ملغاة.'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        if shipment.status == 'delivered' and new_status != 'returned':
            return Response({
                'error': 'الشحنة المسلمة يمكن تغييرها فقط إلى مرتجعة.'
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
            'message': f'تم تحديث حالة الشحنة إلى {new_status}.',
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
    filter_backends = [DjangoFilterBackend, filters.SearchFilter]
    filterset_fields = ['company', 'service_type', 'status', 'sender_address__state', 'receiver_address__state']
    search_fields = ['company__name', 'company__token', 'company__email', 'company__phone', 'carrier__name', 'carrier__username']
    
    def get_queryset(self):
        queryset = Shipment.objects.filter(carrier=self.request.user)
        
        # Note: 'status' filter is now handled by DjangoFilterBackend, 
        # but date range is still custom here.
        
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


class CarrierShipmentStatusUpdateView(generics.GenericAPIView):
    """
    Direct endpoint for carriers to update status of an assigned shipment.
    """
    serializer_class = ShipmentStatusUpdateSerializer
    permission_classes = [IsCarrier]

    def patch(self, request, tracking_number):
        shipment = get_object_or_404(Shipment, tracking_number=tracking_number, carrier=request.user)

        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        new_status = serializer.validated_data['status']
        description = serializer.validated_data.get('description', '')
        location = serializer.validated_data.get('location', '')

        # Use the existing service log/update status
        update_shipment_status(
            shipment=shipment,
            new_status=new_status,
            description=description,
            location=location,
            created_by=request.user
        )

        return Response({
            'message': f'تم تحديث حالة الشحنة إلى {new_status}.',
            'tracking_number': shipment.tracking_number,
            'status': new_status
        })


class CarrierStatusUpdateByScanView(generics.GenericAPIView):
    """
    Scan a shipment to pick it up (self-assign).
    """
    permission_classes = [IsCarrier]
    
    def post(self, request, tracking_number):
        # Find shipment
        shipment = Shipment.objects.filter(tracking_number=tracking_number).first()
        
        if not shipment:
            return Response({
                'error': 'الشحنة غير موجودة.'
            }, status=status.HTTP_404_NOT_FOUND)

        # 1. Company check
        if shipment.company != request.user.company:
            return Response({
                'error': 'الشحنة تابعة لشركة أخرى.'
            }, status=status.HTTP_403_FORBIDDEN)

        # 2. Assignment check
        if shipment.carrier == request.user:
            return Response({
                'error': 'الشحنة معينة لك بالفعل.'
            }, status=status.HTTP_400_BAD_REQUEST)
            
        if shipment.carrier is not None:
            return Response({
                'error': f'الشحنة معينة بالفعل لناقل آخر ({shipment.carrier.username}).'
            }, status=status.HTTP_400_BAD_REQUEST)

        # Perform assignment and update status to picked_up
        shipment.carrier = request.user
        shipment.save(update_fields=['carrier'])

        from .utils import update_shipment_status
        update_shipment_status(
            shipment=shipment,
            new_status='picked_up',
            description='Shipment picked up and assigned to carrier.',
            created_by=request.user
        )
        
        return Response({
            'message': 'تم استلام الشحنة بنجاح.',
            'shipment_id': shipment.id,
            'tracking_number': shipment.tracking_number,
            'status': 'picked_up',
            'assigned_to': request.user.email
        })


class AdminShipmentViewSet(viewsets.ModelViewSet):
    """
    Admin ViewSet for full CRUD on shipments.
    Superuser: Full access.
    Admin: Access only to their company's shipments.
    """
    serializer_class = ShipmentDetailSerializer
    permission_classes = [IsAdmin]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter]
    filterset_fields = ['company', 'carrier', 'service_type', 'status', 'sender_address__state', 'receiver_address__state']
    search_fields = ['company__name', 'company__token', 'company__email', 'company__phone', 'carrier__name', 'carrier__username', 'carrier__email', 'carrier__phone', 'tracking_number', 'reference_number']
    lookup_field = 'id'

    def get_serializer_class(self):
        if self.action in ['create', 'update', 'partial_update']:
            return ShipmentCreateSerializer
        if self.action == 'bulk_assign_carrier':
            return BulkAssignCarrierSerializer
        return ShipmentDetailSerializer

    def get_queryset(self):
        user = self.request.user
        queryset = Shipment.objects.all()
        if user.is_superuser:
            return queryset.order_by('-created_at')
        
        if hasattr(user, 'company') and user.company:
            return queryset.filter(company=user.company).order_by('-created_at')
        return Shipment.objects.none()

    def perform_create(self, serializer):
        # We rely on serializer validation but we need to ensure the user is passed in context
        # (which it is by default in ViewSets).
        # We don't manually assign company here anymore because the serializer create() logic handles it
        # strictly based on superuser/admin status.
        serializer.save()

    @action(detail=False, methods=['post'], url_path='bulk-assign-carrier')
    def bulk_assign_carrier(self, request):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        carrier_id = serializer.validated_data['carrier_id']
        shipment_ids = serializer.validated_data['shipments']

        from accounts.models import User
        try:
            carrier = User.objects.get(id=carrier_id, user_type='carrier')
        except User.DoesNotExist:
            return Response({"error": "الناقل غير موجود."}, status=status.HTTP_404_NOT_FOUND)

        # Security/Requirement Checks
        user = request.user
        if not user.is_superuser:
            if carrier.company != user.company:
                return Response({"error": "الناقل لا ينتمي لشركتك."}, status=status.HTTP_403_FORBIDDEN)

        # Categorize shipments
        successfully_assigned = []
        already_assigned = []
        another_carrier = []
        notfound_shipments = []

        # We'll use IDs that the user actually provided for notfound check
        provided_ids = set(shipment_ids)
        
        # Get accessible shipments
        accessible_qs = Shipment.objects.all()
        if not user.is_superuser:
            accessible_qs = accessible_qs.filter(company=user.company)
            
        found_shipments = accessible_qs.filter(id__in=shipment_ids)
        found_ids = set(found_shipments.values_list('id', flat=True))
        
        # 1. Identify not found
        missing_ids = provided_ids - found_ids
        for mid in missing_ids:
            # We mock the object structure for notfound since it doesn't exist
            notfound_shipments.append(mid)

        # 2. Categorize found shipments
        for shipment in found_shipments:
            # For superuser, carrier and shipment company MUST match
            if user.is_superuser and shipment.company != carrier.company:
                notfound_shipments.append(shipment.id)
                continue

            if shipment.carrier == carrier:
                already_assigned.append(shipment)
            elif shipment.carrier is not None:
                another_carrier.append(shipment)
            else:
                # Unassigned or we reassign (decided to reassign only if None in previous logic, 
                # but user prompt implies we assign if not already assigned or for another)
                shipment.carrier = carrier
                shipment.save(update_fields=['carrier'])
                
                # Create tracking event
                TrackingEvent.objects.create(
                    shipment=shipment,
                    status=shipment.status,
                    description=f'Shipment assigned to carrier: {carrier.name or carrier.username}',
                    created_by=user
                )
                successfully_assigned.append(shipment)

        # Serialize everything
        detail_serializer = ShipmentDetailSerializer
        
        return Response({
            "message": f"تم تعيين {len(successfully_assigned)} شحنة بنجاح للناقل {carrier.name or carrier.username}.",
            "carrier_id": carrier_id,
            "successfully_assigned_shipments": detail_serializer(successfully_assigned, many=True).data,
            "already_assigned_for_this_caarier": detail_serializer(already_assigned, many=True).data,
            "assigne_for_another_carrier": detail_serializer(another_carrier, many=True).data,
            "notfound_shpments": notfound_shipments 
        })


# ─────────────────────────────────────────────────────────────────
# SIMPLE LIST ENDPOINTS (Dropdowns/Selectors)
# ─────────────────────────────────────────────────────────────────

class SimpleServiceTypeListView(generics.ListAPIView):
    """
    List Service Types (Simple).
    Superuser: All.
    Admin: Their company only.
    Returns: id, name, code.
    """
    permission_classes = [IsAdmin]
    serializer_class = SimpleServiceTypeSerializer
    pagination_class = None
    filter_backends = [DjangoFilterBackend, filters.SearchFilter]
    filterset_fields = ['company']

    def get_queryset(self):
        user = self.request.user
        if user.is_superuser:
            return ServiceType.objects.all().order_by('name')
        if hasattr(user, 'company') and user.company:
            return ServiceType.objects.filter(company=user.company).order_by('name')
        return ServiceType.objects.none()


class SimpleShipmentListView(generics.ListAPIView):
    """
    List Shipments (Simple).
    Superuser: All.
    Admin: Their company only.
    Returns: id, reference_number, tracking_number.
    """
    permission_classes = [IsAdmin]
    serializer_class = SimpleShipmentSerializer
    pagination_class = None
    filter_backends = [DjangoFilterBackend, filters.SearchFilter]
    filterset_fields = ['company']
    

    def get_queryset(self):
        user = self.request.user
        if user.is_superuser:
            return Shipment.objects.all().order_by('-created_at')
        if hasattr(user, 'company') and user.company:
            return Shipment.objects.filter(company=user.company).order_by('-created_at')
        return Shipment.objects.none()


class SimpleWebhookListView(generics.ListAPIView):
    """
    List Webhooks (Simple).
    Superuser: All.
    Admin: Their company only.
    Returns: id, url, is_active.
    """
    permission_classes = [IsAdmin]
    serializer_class = SimpleWebhookSerializer
    pagination_class = None
    filter_backends = [DjangoFilterBackend, filters.SearchFilter]
    filterset_fields = ['company']

    def get_queryset(self):
        user = self.request.user
        if user.is_superuser:
            return Webhook.objects.all().order_by('-created_at')
        if hasattr(user, 'company') and user.company:
            return Webhook.objects.filter(company=user.company).order_by('-created_at')
        return Webhook.objects.none()


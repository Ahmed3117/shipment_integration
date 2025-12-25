from rest_framework import generics, status
from rest_framework.response import Response
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.views import APIView
from django.contrib.auth import get_user_model
from django.shortcuts import get_object_or_404

from .models import Company
from .serializers import (
    UserRegistrationSerializer, 
    UserSerializer,
    UserListSerializer,
    CarrierSerializer,
    AdminUserRegistrationSerializer,
    CompanySerializer,
    CompanyCreateSerializer,
    CompanyDetailSerializer,
    CompanyTokenSerializer,
    CompanyListWithTokenSerializer,
    UserUpdateSerializer,
    SimpleCompanySerializer,
    SimpleUserSerializer,
)

from shipments.permissions import IsAdmin, IsSuperuser, IsCarrierOrAdmin
from rest_framework import filters
from django_filters.rest_framework import DjangoFilterBackend

User = get_user_model()


# ─────────────────────────────────────────────────────────────────
# SUPERUSER ONLY ENDPOINTS
# ─────────────────────────────────────────────────────────────────

class SuperuserCompanyListCreateView(generics.ListCreateAPIView):
    """
    List all companies or create a new company.
    Superuser only.
    """
    queryset = Company.objects.all()
    permission_classes = [IsSuperuser]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter]
    filterset_fields = ['is_active']
    search_fields = ['name', 'phone', 'email', 'token']
    
    def get_serializer_class(self):
        if self.request.method == 'POST':
            return CompanyCreateSerializer
        return CompanyListWithTokenSerializer
    
    def get_queryset(self):
        queryset = Company.objects.all()
        is_active = self.request.query_params.get('is_active')
        if is_active is not None:
            queryset = queryset.filter(is_active=is_active.lower() == 'true')
        return queryset.order_by('-created_at')
    
    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        company = serializer.save()
        
        return Response({
            'message': 'تم إنشاء الشركة بنجاح.',
            'company': CompanyDetailSerializer(company).data
        }, status=status.HTTP_201_CREATED)


class SuperuserCompanyDetailView(generics.RetrieveUpdateDestroyAPIView):
    """
    Get, update, or delete a company.
    Superuser only.
    """
    queryset = Company.objects.all()
    serializer_class = CompanyDetailSerializer
    permission_classes = [IsSuperuser]
    
    def destroy(self, request, *args, **kwargs):
        instance = self.get_object()
        from shipments.models import Shipment
        shipment_count = Shipment.objects.filter(company=instance).count()
        if shipment_count > 0:
            return Response({
                'error': f'لا يمكن حذف الشركة. لديها {shipment_count} شحنة (شحنات).',
                'suggestion': 'فكر في إلغاء تنشيط الشركة بدلاً من ذلك.'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        self.perform_destroy(instance)
        return Response({
            'message': 'تم حذف الشركة بنجاح.'
        }, status=status.HTTP_200_OK)


class SuperuserCompanyRegenerateTokenView(APIView):
    """
    Regenerate API token for a company.
    Superuser only.
    """
    permission_classes = [IsSuperuser]
    
    def post(self, request, pk):
        company = get_object_or_404(Company, pk=pk)
        company.regenerate_token()
        
        return Response({
            'message': 'تم إعادة إنشاء رمز API بنجاح.',
            'company': CompanyTokenSerializer(company).data
        })


class SuperuserAdminUserCreateView(generics.CreateAPIView):
    """
    Create a new admin user.
    Superuser only - this is a critical operation.
    """
    serializer_class = AdminUserRegistrationSerializer
    permission_classes = [IsSuperuser]
    
    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.save()
        
        return Response({
            'message': 'تم إنشاء المستخدم المسؤول بنجاح.',
            'user': UserSerializer(user).data
        }, status=status.HTTP_201_CREATED)


class SuperuserUserListView(generics.ListAPIView):
    """
    List all users including admins.
    Superuser only.
    """
    queryset = User.objects.all()
    serializer_class = UserListSerializer
    permission_classes = [IsSuperuser]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter]
    filterset_fields = ['user_type', 'company']
    search_fields = ['company__name', 'name', 'phone', 'email', 'username']
    
    def get_queryset(self):
        queryset = User.objects.all()
        user_type = self.request.query_params.get('user_type')
        if user_type:
            queryset = queryset.filter(user_type=user_type)
        return queryset.order_by('-date_joined')


class SuperuserUserDetailView(generics.RetrieveUpdateDestroyAPIView):
    """
    Get, update, or delete any user (including admins).
    Superuser only.
    """
    queryset = User.objects.all()
    serializer_class = UserSerializer
    permission_classes = [IsSuperuser]
    
    def get_serializer_class(self):
        if self.request.method in ['PATCH', 'PUT']:
            return UserUpdateSerializer
        return UserSerializer
    
    def destroy(self, request, *args, **kwargs):
        instance = self.get_object()
        if instance == request.user:
            return Response({
                'error': 'لا يمكنك حذف حسابك الخاص.'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        if instance.is_superuser:
            return Response({
                'error': 'لا يمكن حذف حساب مسؤول متميز آخر.'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        self.perform_destroy(instance)
        return Response({
            'message': 'تم حذف المستخدم بنجاح.'
        }, status=status.HTTP_200_OK)


# ─────────────────────────────────────────────────────────────────
# COMPANY MANAGEMENT (Admin Only - Read + limited actions)
# ─────────────────────────────────────────────────────────────────

class CompanyListCreateView(generics.ListAPIView):
    """
    List all companies.
    Admin only (read access).
    """
    queryset = Company.objects.all()
    serializer_class = CompanySerializer
    permission_classes = [IsAdmin]
    
    def get_queryset(self):
        user = self.request.user
        # Superuser can see all companies, admin only their own
        if user.is_superuser:
            queryset = Company.objects.all()
        else:
            queryset = Company.objects.filter(id=user.company_id)
        is_active = self.request.query_params.get('is_active')
        if is_active is not None:
            queryset = queryset.filter(is_active=is_active.lower() == 'true')
        return queryset.order_by('-created_at')


class CompanyDetailView(generics.RetrieveAPIView):
    """
    Get company details.
    Admin only (read access).
    """
    serializer_class = CompanyDetailSerializer
    permission_classes = [IsAdmin]

    def get_queryset(self):
        user = self.request.user
        if user.is_superuser:
            return Company.objects.all()
        return Company.objects.filter(id=user.company_id)


class CompanyRegenerateTokenView(APIView):
    """
    Regenerate API token for a company.
    Admin only.
    """
    permission_classes = [IsAdmin]

    def post(self, request, pk):
        user = request.user
        # Only allow if user is superuser or company matches
        if user.is_superuser:
            company = get_object_or_404(Company, pk=pk)
        else:
            if user.company_id != pk:
                return Response({'error': 'ليس لديك إذن لإعادة إنشاء الرمز المميز لهذه الشركة.'}, status=403)
            company = get_object_or_404(Company, pk=pk)
        company.regenerate_token()
        return Response({
            'message': 'تم إعادة إنشاء رمز API بنجاح.',
            'company': CompanyTokenSerializer(company).data
        })


# ─────────────────────────────────────────────────────────────────
# USER MANAGEMENT (Admin Only - carriers only, not admins)
# ─────────────────────────────────────────────────────────────────

class UserListCreateView(generics.ListCreateAPIView):
    """
    List carrier users or create a new carrier.
    Admin only. To create admin users, use superuser endpoints.
    """

    permission_classes = [IsAdmin]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter]
    filterset_fields = ['user_type', 'company']
    search_fields = ['company__name', 'name', 'phone', 'email', 'username']
    
    def get_serializer_class(self):
        if self.request.method == 'POST':
            return UserRegistrationSerializer
        return UserListSerializer
    
    def get_queryset(self):
        user = self.request.user
        queryset = User.objects.filter(user_type='carrier')
        
        # Admin can only see carriers in their company
        if not user.is_superuser:
            queryset = queryset.filter(company_id=user.company_id)
            
        # Support filtering by company ID
        company = self.request.query_params.get('company')
        if company:
            queryset = queryset.filter(company_id=company)
            
        return queryset.order_by('-date_joined')
    
    def create(self, request, *args, **kwargs):
        # Force user_type to carrier - admins cannot create admin users
        data = request.data.copy()
        data['user_type'] = 'carrier'
        
        serializer = self.get_serializer(data=data)
        serializer.is_valid(raise_exception=True)
        user = serializer.save()
        
        return Response({
            'message': 'تم إنشاء المستخدم الناقل بنجاح.',
            'user': UserSerializer(user).data
        }, status=status.HTTP_201_CREATED)


class UserDetailView(generics.RetrieveUpdateDestroyAPIView):
    """
    Get, update, or delete a carrier user.
    Admin only. Cannot modify admin users.
    """
    serializer_class = UserSerializer
    permission_classes = [IsAdmin]
    
    def get_serializer_class(self):
        if self.request.method in ['PATCH', 'PUT']:
            return UserUpdateSerializer
        return UserSerializer
    
    def get_queryset(self):
        user = self.request.user
        queryset = User.objects.filter(user_type='carrier')
        if user.is_superuser:
            return queryset
        return queryset.filter(company_id=user.company_id)
    
    def destroy(self, request, *args, **kwargs):
        instance = self.get_object()
        self.perform_destroy(instance)
        return Response({
            'message': 'تم حذف المستخدم بنجاح.'
        }, status=status.HTTP_200_OK)


class CarrierListView(generics.ListAPIView):
    """
    List all carrier users.
    Admin only.
    """
    serializer_class = CarrierSerializer
    permission_classes = [IsAdmin]
    
    def get_queryset(self):
        user = self.request.user
        queryset = User.objects.filter(user_type='carrier')
        
        # Admin can only see carriers in their company
        if not user.is_superuser:
            queryset = queryset.filter(company_id=user.company_id)
            
        # Support filtering by company ID
        company = self.request.query_params.get('company')
        if company:
            queryset = queryset.filter(company_id=company)
            
        return queryset.order_by('username')



# ─────────────────────────────────────────────────────────────────
# SIMPLE LIST ENDPOINTS (Dropdowns/Selectors)
# ─────────────────────────────────────────────────────────────────

class SimpleAdminListView(generics.ListAPIView):
    """
    List all Admins.
    Superuser Only.
    Returns: id, username, name.
    """
    permission_classes = [IsSuperuser]
    serializer_class = SimpleUserSerializer

    def get_queryset(self):
        return User.objects.filter(user_type='admin').order_by('username')


class SimpleStaffListView(generics.ListAPIView):
    """
    List all Staff.
    Superuser Only.
    Returns: id, username, name.
    """
    permission_classes = [IsSuperuser]
    serializer_class = SimpleUserSerializer

    def get_queryset(self):
        return User.objects.filter(user_type='staff').order_by('username')



class SimpleCarrierListView(generics.ListAPIView):
    """
    List all Carriers.
    Superuser: All carriers.
    Admin: Carriers of their company.
    Returns: id, username, name.
    """
    permission_classes = [IsAdmin]
    serializer_class = SimpleUserSerializer

    def get_queryset(self):
        user = self.request.user
        qs = User.objects.filter(user_type='carrier')
        if not user.is_superuser:
            qs = qs.filter(company_id=user.company_id)
        return qs.order_by('username')


class SimpleCompanyListView(generics.ListAPIView):
    """
    List all Companies.
    Superuser: All companies.
    Admin: Their own company only.
    Returns: id, name.
    """
    permission_classes = [IsAdmin]
    serializer_class = SimpleCompanySerializer

    def get_queryset(self):
        user = self.request.user
        if user.is_superuser:
            return Company.objects.all().order_by('name')
        return Company.objects.filter(id=user.company_id)


# ─────────────────────────────────────────────────────────────────
# USER PROFILE
# ─────────────────────────────────────────────────────────────────

class UserProfileView(generics.RetrieveUpdateAPIView):
    """Retrieve or update current user profile."""
    permission_classes = [IsAuthenticated]
    
    def get_serializer_class(self):
        if self.request.method in ['PATCH', 'PUT']:
            return UserUpdateSerializer
        return UserSerializer
    
    def update(self, request, *args, **kwargs):
        # Prevent non-superusers from updating their own company
        if not request.user.is_superuser:
            if 'company_id' in request.data:
                # We could either ignore it or return an error. 
                # The requirement says "except the company", so let's ignore or error.
                # I'll just remove it from the data to be safe.
                data = request.data.copy()
                data.pop('company_id', None)
                request._full_data = data # This is a bit hacky for DRF, let's use a cleaner way
        
        return super().update(request, *args, **kwargs)
    
    def perform_update(self, serializer):
        # If not superuser, remove company_id from validated_data
        if not self.request.user.is_superuser:
            serializer.validated_data.pop('company_id', None)
        serializer.save()
    
    def get_object(self):
        return self.request.user

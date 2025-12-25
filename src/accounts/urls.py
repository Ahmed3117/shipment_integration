from django.urls import path
from rest_framework_simplejwt.views import TokenRefreshView, TokenObtainPairView

from .serializers import CustomTokenObtainPairSerializer
from .views import (
    UserProfileView,
    # Superuser endpoints
    SuperuserCompanyListCreateView,
    SuperuserCompanyDetailView,
    SuperuserCompanyRegenerateTokenView,
    SuperuserAdminUserCreateView,
    SuperuserUserListView,
    SuperuserUserDetailView,
    # Admin endpoints
    CompanyListCreateView,
    CompanyDetailView,
    CompanyRegenerateTokenView,
    UserListCreateView,
    UserDetailView,
    CarrierListView,
    SimpleAdminListView,
    SimpleStaffListView,
    SimpleCarrierListView,
    SimpleCompanyListView,
)


# Custom JWT view that returns full user data
class CustomTokenObtainPairView(TokenObtainPairView):
    serializer_class = CustomTokenObtainPairSerializer


urlpatterns = [
    # JWT Authentication (for carriers/admins) - Returns full user data
    path('login/', CustomTokenObtainPairView.as_view(), name='token_obtain_pair'),
    path('token/refresh/', TokenRefreshView.as_view(), name='token_refresh'),
    
    # Authenticated user profile
    path('profile/', UserProfileView.as_view(), name='profile'),
    
    # ─────────────────────────────────────────────────────────────────
    # SUPERUSER ENDPOINTS - Critical Operations
    # ─────────────────────────────────────────────────────────────────
    path('superuser/companies/', SuperuserCompanyListCreateView.as_view(), name='superuser-company-list-create'),
    path('superuser/companies/<int:pk>/', SuperuserCompanyDetailView.as_view(), name='superuser-company-detail'),
    path('superuser/companies/<int:pk>/regenerate-token/', SuperuserCompanyRegenerateTokenView.as_view(), name='superuser-company-regenerate-token'),
    path('superuser/admins/', SuperuserAdminUserCreateView.as_view(), name='superuser-admin-create'),
    path('superuser/users/', SuperuserUserListView.as_view(), name='superuser-user-list'),
    path('superuser/users/<int:pk>/', SuperuserUserDetailView.as_view(), name='superuser-user-detail'),
    
    # ─────────────────────────────────────────────────────────────────
    # ADMIN ENDPOINTS - Company Management (Read + regenerate token)
    # ─────────────────────────────────────────────────────────────────
    path('admin/companies/', CompanyListCreateView.as_view(), name='company-list'),
    path('admin/companies/<int:pk>/', CompanyDetailView.as_view(), name='company-detail'),
    path('admin/companies/<int:pk>/regenerate-token/', CompanyRegenerateTokenView.as_view(), name='company-regenerate-token'),
    
    # ─────────────────────────────────────────────────────────────────
    # ADMIN ENDPOINTS - Carrier Management (CRUD carriers only)
    # ─────────────────────────────────────────────────────────────────
    path('admin/carriers/', UserListCreateView.as_view(), name='user-list-create'),
    path('admin/carriers/<int:pk>/', UserDetailView.as_view(), name='user-detail'),


    # ─────────────────────────────────────────────────────────────────
    # SIMPLE LIST ENDPOINTS (Selects/Dropdowns)
    # ─────────────────────────────────────────────────────────────────
    path('simple/admins/', SimpleAdminListView.as_view(), name='simple-admin-list'),
    path('simple/staff/', SimpleStaffListView.as_view(), name='simple-staff-list'),
    path('simple/carriers/', SimpleCarrierListView.as_view(), name='simple-carrier-list'),
    path('simple/companies/', SimpleCompanyListView.as_view(), name='simple-company-list'),
]

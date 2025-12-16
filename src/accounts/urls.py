from django.urls import path
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView

from .views import (
    UserRegistrationView, 
    UserProfileView,
    PendingApprovalsListView,
    UserApprovalView,
    ApprovedUsersListView,
)

urlpatterns = [
    # Public endpoints
    path('register/', UserRegistrationView.as_view(), name='register'),
    path('login/', TokenObtainPairView.as_view(), name='token_obtain_pair'),
    path('token/refresh/', TokenRefreshView.as_view(), name='token_refresh'),
    
    # Authenticated user endpoints
    path('profile/', UserProfileView.as_view(), name='profile'),
    
    # Admin endpoints for user management
    path('admin/pending-approvals/', PendingApprovalsListView.as_view(), name='pending-approvals'),
    path('admin/users/<int:user_id>/approve/', UserApprovalView.as_view(), name='user-approval'),
    path('admin/approved-users/', ApprovedUsersListView.as_view(), name='approved-users'),
]

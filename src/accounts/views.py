from rest_framework import generics, status
from rest_framework.response import Response
from rest_framework.permissions import AllowAny, IsAdminUser
from rest_framework.views import APIView
from django.contrib.auth import get_user_model
from django.utils import timezone
from django.shortcuts import get_object_or_404

from .serializers import (
    UserRegistrationSerializer, 
    UserSerializer, 
    UserApprovalSerializer,
    PendingUserSerializer
)

User = get_user_model()


class UserRegistrationView(generics.CreateAPIView):
    """Register a new user (company account)."""
    queryset = User.objects.all()
    serializer_class = UserRegistrationSerializer
    permission_classes = [AllowAny]
    
    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.save()
        
        # Different message based on user type
        if user.user_type == 'customer':
            message = (
                'Registration submitted successfully. '
                'Your account is pending approval. '
                'You will be notified once your account is reviewed and activated.'
            )
        else:
            message = 'User registered successfully.'
        
        return Response({
            'message': message,
            'user': UserSerializer(user).data
        }, status=status.HTTP_201_CREATED)


class UserProfileView(generics.RetrieveUpdateAPIView):
    """Retrieve or update user profile."""
    serializer_class = UserSerializer
    
    def get_object(self):
        return self.request.user


# ─────────────────────────────────────────────────────────────────
# ADMIN ENDPOINTS FOR USER APPROVAL
# ─────────────────────────────────────────────────────────────────

class PendingApprovalsListView(generics.ListAPIView):
    """
    List all pending customer accounts awaiting approval.
    Admin only.
    """
    serializer_class = PendingUserSerializer
    permission_classes = [IsAdminUser]
    
    def get_queryset(self):
        return User.objects.filter(
            user_type='customer',
            is_active=False,
            is_approved=False
        ).order_by('-date_joined')


class UserApprovalView(APIView):
    """
    Approve or reject a pending customer account.
    Admin only.
    """
    permission_classes = [IsAdminUser]
    
    def post(self, request, user_id):
        user = get_object_or_404(User, pk=user_id, user_type='customer')
        
        # Check if already processed
        if user.is_approved:
            return Response({
                'error': 'This account has already been approved.'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        serializer = UserApprovalSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        action = serializer.validated_data['action']
        
        if action == 'approve':
            user.is_active = True
            user.is_approved = True
            user.approved_at = timezone.now()
            user.approved_by = request.user
            user.rejection_reason = ''
            user.save()
            
            # TODO: Send approval email to user
            
            return Response({
                'message': f'Account for {user.company_name} has been approved.',
                'user': UserSerializer(user).data
            })
        
        else:  # reject
            user.rejection_reason = serializer.validated_data.get('rejection_reason', '')
            user.save()
            
            # TODO: Send rejection email to user
            
            return Response({
                'message': f'Account for {user.company_name} has been rejected.',
                'rejection_reason': user.rejection_reason
            })


class ApprovedUsersListView(generics.ListAPIView):
    """
    List all approved customer accounts.
    Admin only.
    """
    serializer_class = UserSerializer
    permission_classes = [IsAdminUser]
    
    def get_queryset(self):
        return User.objects.filter(
            user_type='customer',
            is_approved=True
        ).order_by('-approved_at')

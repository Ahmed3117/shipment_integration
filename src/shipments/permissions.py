from rest_framework import permissions
from accounts.authentication import CompanyUser


class IsSuperuser(permissions.BasePermission):
    """
    Permission check for superusers only.
    Used for critical operations like creating admin users.
    """
    message = 'You must be a superuser to access this resource.'
    
    def has_permission(self, request, view):
        return (
            request.user and 
            request.user.is_authenticated and 
            not isinstance(request.user, CompanyUser) and
            request.user.is_superuser
        )


class IsAdmin(permissions.BasePermission):
    """
    Permission check for admin users only.
    Regular admins can only access their own company's data.
    """
    message = 'You must be an admin to access this resource.'
    
    def has_permission(self, request, view):
        user = request.user
        if not user or not user.is_authenticated:
            return False
            
        if isinstance(user, CompanyUser):
            return False
            
        return user.user_type in ['admin', 'staff'] or user.is_staff or user.is_superuser


class IsCarrier(permissions.BasePermission):
    """
    Permission check for carrier users.
    """
    message = 'You must be a carrier to access this resource.'
    
    def has_permission(self, request, view):
        return (
            request.user and 
            request.user.is_authenticated and 
            not isinstance(request.user, CompanyUser) and
            request.user.user_type == 'carrier'
        )


class IsCompany(permissions.BasePermission):
    """
    Permission check for Company token authentication.
    """
    message = 'You must authenticate with a valid company API token.'
    
    def has_permission(self, request, view):
        return (
            request.user and 
            request.user.is_authenticated and 
            isinstance(request.user, CompanyUser)
        )


class IsCompanyOrAdmin(permissions.BasePermission):
    """
    Permission check for Company token or Admin user.
    """
    message = 'You must be a company or admin to access this resource.'
    
    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False
        
        # Company token auth
        if isinstance(request.user, CompanyUser):
            return True
        
        # Admin/Staff/Superuser
        return request.user.user_type == 'admin' or request.user.is_staff or request.user.is_superuser


class IsCarrierOrAdmin(permissions.BasePermission):
    """
    Permission check for carrier or admin users.
    """
    message = 'You must be a carrier or admin to access this resource.'
    
    def has_permission(self, request, view):
        return (
            request.user and 
            request.user.is_authenticated and 
            not isinstance(request.user, CompanyUser) and
            request.user.user_type in ['carrier', 'admin', 'staff']
        )

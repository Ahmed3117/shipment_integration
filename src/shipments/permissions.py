from rest_framework import permissions


class IsAdmin(permissions.BasePermission):
    """
    Permission check for admin users only.
    """
    message = 'You must be an admin to access this resource.'
    
    def has_permission(self, request, view):
        return (
            request.user and 
            request.user.is_authenticated and 
            (request.user.user_type == 'admin' or request.user.is_staff)
        )


class IsCarrier(permissions.BasePermission):
    """
    Permission check for carrier users.
    """
    message = 'You must be a carrier to access this resource.'
    
    def has_permission(self, request, view):
        return (
            request.user and 
            request.user.is_authenticated and 
            request.user.user_type == 'carrier'
        )


class IsCustomer(permissions.BasePermission):
    """
    Permission check for customer users.
    """
    message = 'You must be a customer to access this resource.'
    
    def has_permission(self, request, view):
        return (
            request.user and 
            request.user.is_authenticated and 
            request.user.user_type == 'customer'
        )


class IsCarrierOrAdmin(permissions.BasePermission):
    """
    Permission check for carrier or admin users.
    """
    message = 'You must be a carrier or admin to access this resource.'
    
    def has_permission(self, request, view):
        return (
            request.user and 
            request.user.is_authenticated and 
            request.user.user_type in ['carrier', 'admin']
        )

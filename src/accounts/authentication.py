"""
Custom authentication for Company token-based authentication.

Companies authenticate using their API token in the header:
    Authorization: Token <company_token>

Users (carriers/admins) authenticate using JWT tokens.
"""

from rest_framework import authentication, exceptions
from django.utils.translation import gettext_lazy as _
from .models import Company


class CompanyTokenAuthentication(authentication.BaseAuthentication):
    """
    Token-based authentication for Company API access.
    
    Clients should authenticate by passing the token key in the "Authorization"
    HTTP header, prepended with the string "Token ".  For example:

        Authorization: Token 9944b09199c62bcf9418ad846dd0e4bbdfc6ee4b
    """
    
    keyword = 'Token'
    
    def authenticate(self, request):
        # 1. Check for X-Company-Token header
        token = request.META.get('HTTP_X_COMPANY_TOKEN')
        if token:
            return self.authenticate_credentials(token)

        # 2. Fallback to standard Authorization header
        auth_header = authentication.get_authorization_header(request).split()
        
        if not auth_header:
            return None
        
        if len(auth_header) == 1:
            msg = _('Invalid token header. No credentials provided.')
            raise exceptions.AuthenticationFailed(msg)
        
        if len(auth_header) > 2:
            msg = _('Invalid token header. Token string should not contain spaces.')
            raise exceptions.AuthenticationFailed(msg)
        
        try:
            token = auth_header[1].decode('utf-8')
        except UnicodeDecodeError:
            msg = _('Invalid token header. Token string should not contain invalid characters.')
            raise exceptions.AuthenticationFailed(msg)
        
        # Check if it's a Token authentication
        prefix = auth_header[0].decode('utf-8')
        if prefix.lower() != self.keyword.lower():
            return None
        
        return self.authenticate_credentials(token)
    
    def authenticate_credentials(self, token):
        """
        Validate the company token and return the company if valid.
        """
        try:
            company = Company.objects.get(token=token)
        except Company.DoesNotExist:
            raise exceptions.AuthenticationFailed(_('Invalid token.'))
        
        if not company.is_active:
            raise exceptions.AuthenticationFailed(_('Company account is not active.'))
        
        # Return (company, token) - company acts as the "user" for request.user
        # We use a custom wrapper to distinguish company from user
        return (CompanyUser(company), token)
    
    def authenticate_header(self, request):
        return self.keyword


class CompanyUser:
    """
    Wrapper class to represent a Company as a user-like object.
    This allows using request.user in views while distinguishing
    between Company (token) and User (JWT) authentication.
    """
    
    def __init__(self, company):
        self.company = company
        self.id = company.id
        self.pk = company.id
        self.is_authenticated = True
        self.is_company = True
        self.is_superuser = False
        self.is_staff = False
        
    def __str__(self):
        return f"Company: {self.company.name}"
    
    @property
    def name(self):
        return self.company.name
    
    @property
    def email(self):
        return self.company.email

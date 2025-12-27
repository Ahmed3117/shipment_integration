from rest_framework import serializers
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer
from django.contrib.auth import get_user_model
from django.contrib.auth.password_validation import validate_password

from .models import Company

User = get_user_model()


# ─────────────────────────────────────────────────────────────────
# CUSTOM JWT SERIALIZER
# ─────────────────────────────────────────────────────────────────

class CustomTokenObtainPairSerializer(TokenObtainPairSerializer):
    """Custom JWT serializer that returns full user data with tokens."""
    
    def validate(self, attrs):
        data = super().validate(attrs)
        
        # Add full user data to the response
        user = self.user
        data['user'] = {
            'id': user.id,
            'username': user.username,
            'email': user.email,
            'name': user.name,
            'user_type': user.user_type,
            'phone': user.phone,
            'is_active': user.is_active,
            'is_staff': user.is_staff,
            'is_superuser': user.is_superuser,
            'date_joined': user.date_joined.isoformat() if user.date_joined else None,
            'last_login': user.last_login.isoformat() if user.last_login else None,
            'company': {
                'id': user.company.id,
                'name': user.company.name,
            } if user.company else None,
        }
        
        return data


# ─────────────────────────────────────────────────────────────────
# COMPANY SERIALIZERS
# ─────────────────────────────────────────────────────────────────

class SimpleCompanySerializer(serializers.ModelSerializer):
    """Simple serializer for listing companies."""
    class Meta:
        model = Company
        fields = ['id', 'name']


class CompanySerializer(serializers.ModelSerializer):
    """Serializer for Company model (read-only for public use)."""
    class Meta:
        model = Company
        fields = ['id', 'name', 'email', 'phone', 'is_active', 'created_at']
        read_only_fields = fields


class CompanyListWithTokenSerializer(serializers.ModelSerializer):
    """Serializer for Company list with token (superuser only)."""
    class Meta:
        model = Company
        fields = ['id', 'name', 'email', 'phone', 'token', 'is_active', 'created_at', 'updated_at']
        read_only_fields = fields


class CompanyCreateSerializer(serializers.ModelSerializer):
    """Serializer for creating a new Company (admin only)."""
    class Meta:
        model = Company
        fields = ['id', 'name', 'email', 'phone', 'is_active', 'token', 'created_at']
        read_only_fields = ['id', 'token', 'created_at']
        extra_kwargs = {
            'email': {'required': True},
            'name': {'required': True},
        }
    
    def validate_email(self, value):
        if Company.objects.filter(email=value).exists():
            raise serializers.ValidationError('A company with this email already exists.')
        return value


class CompanyDetailSerializer(serializers.ModelSerializer):
    """Serializer for Company details including token (admin only)."""
    class Meta:
        model = Company
        fields = ['id', 'name', 'email', 'phone', 'token', 'is_active', 'created_at', 'updated_at']
        read_only_fields = ['id', 'token', 'created_at', 'updated_at']


class CompanyTokenSerializer(serializers.ModelSerializer):
    """Serializer to show company token (used after company creation)."""
    class Meta:
        model = Company
        fields = ['id', 'name', 'token']
        read_only_fields = fields


# ─────────────────────────────────────────────────────────────────
# USER SERIALIZERS (Carrier/Admin only)
# ─────────────────────────────────────────────────────────────────

class UserRegistrationSerializer(serializers.ModelSerializer):
    """Serializer for admin to create carrier users only."""
    password = serializers.CharField(write_only=True, validators=[validate_password])
    password_confirm = serializers.CharField(write_only=True)
    company_id = serializers.IntegerField(required=False, allow_null=True)
    
    class Meta:
        model = User
        fields = ['id', 'username', 'email', 'name', 'password', 'password_confirm', 'company_id', 'phone']
        extra_kwargs = {
            'email': {'required': True},
        }
    
    def validate(self, attrs):
        if attrs['password'] != attrs['password_confirm']:
            raise serializers.ValidationError({'password_confirm': 'Passwords do not match.'})
        return attrs
    
    def validate_company_id(self, value):
        if value:
            try:
                Company.objects.get(id=value)
            except Company.DoesNotExist:
                raise serializers.ValidationError('Company not found.')
        return value
    
    def create(self, validated_data):
        validated_data.pop('password_confirm')
        company_id = validated_data.pop('company_id', None)
        
        # Force carrier type - this serializer is only for carrier creation
        validated_data['user_type'] = 'carrier'
        
        if company_id:
            validated_data['company'] = Company.objects.get(id=company_id)
        
        user = User.objects.create_user(**validated_data)
        return user


class AdminUserRegistrationSerializer(serializers.ModelSerializer):
    """Serializer for superuser to create admin users. SUPERUSER ONLY."""
    password = serializers.CharField(write_only=True, validators=[validate_password])
    password_confirm = serializers.CharField(write_only=True)
    is_staff = serializers.BooleanField(default=True)
    company_id = serializers.IntegerField(required=False, allow_null=True)
    
    class Meta:
        model = User
        fields = ['id', 'username', 'email', 'name', 'password', 'password_confirm', 'phone', 'is_staff', 'company_id']
        extra_kwargs = {
            'email': {'required': True},
        }
    
    def validate(self, attrs):
        if attrs['password'] != attrs['password_confirm']:
            raise serializers.ValidationError({'password_confirm': 'Passwords do not match.'})
        return attrs
    
    def validate_company_id(self, value):
        if value:
            try:
                Company.objects.get(id=value)
            except Company.DoesNotExist:
                raise serializers.ValidationError('Company not found.')
        return value
    
    def create(self, validated_data):
        validated_data.pop('password_confirm')
        company_id = validated_data.pop('company_id', None)
        validated_data['user_type'] = 'admin'
        validated_data['is_staff'] = validated_data.get('is_staff', True)
        
        if company_id:
            validated_data['company'] = Company.objects.get(id=company_id)
        
        user = User.objects.create_user(**validated_data)
        return user


class UserSerializer(serializers.ModelSerializer):
    """Serializer for User details."""
    company = CompanySerializer(read_only=True)
    
    class Meta:
        model = User
        fields = ['id', 'username', 'email', 'name', 'user_type', 'company', 'phone', 
                  'is_active', 'is_staff', 'is_superuser', 'date_joined', 'last_login']
        read_only_fields = ['id', 'username', 'user_type', 'is_active', 'is_staff', 
                           'is_superuser', 'date_joined', 'last_login']


class UserListSerializer(serializers.ModelSerializer):
    """Serializer for listing users (admin view)."""
    company_name = serializers.CharField(source='company.name', read_only=True, allow_null=True)
    
    class Meta:
        model = User
        fields = ['id', 'username', 'email', 'name', 'user_type', 'company', 'company_name', 'phone', 'is_active', 'date_joined']
        read_only_fields = fields



class SimpleUserSerializer(serializers.ModelSerializer):
    """Simple serializer for listing users."""
    class Meta:
        model = User
        fields = ['id', 'username', 'name']


class CarrierSerializer(serializers.ModelSerializer):
    """Serializer for carrier users."""
    company_name = serializers.CharField(source='company.name', read_only=True, allow_null=True)
    
    class Meta:
        model = User
        fields = ['id', 'username', 'email', 'name', 'company_name', 'phone', 'is_active']
        read_only_fields = fields


class UserUpdateSerializer(serializers.ModelSerializer):
    """
    Serializer for updating user details.
    Handles password hashing correctly if password is provided.
    """
    password = serializers.CharField(write_only=True, required=False, validators=[validate_password])
    company_id = serializers.IntegerField(required=False, allow_null=True)
    
    class Meta:
        model = User
        fields = ['username', 'email', 'name', 'phone', 'password', 'company_id', 'is_active']
    
    def update(self, instance, validated_data):
        password = validated_data.pop('password', None)
        company_id = validated_data.pop('company_id', None)
        
        # Update other fields
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
            
        # Handle password update
        if password:
            instance.set_password(password)
            
        # Handle company update
        if company_id is not None:
            # Check if company exists if it was passed
            try:
                company = Company.objects.get(id=company_id)
                instance.company = company
            except Company.DoesNotExist:
                raise serializers.ValidationError({'company_id': 'Company not found.'})
        
        instance.save()
        return instance

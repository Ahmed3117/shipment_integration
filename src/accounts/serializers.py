from rest_framework import serializers
from django.contrib.auth import get_user_model
from django.contrib.auth.password_validation import validate_password

User = get_user_model()


class UserRegistrationSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True, validators=[validate_password])
    password_confirm = serializers.CharField(write_only=True)
    user_type = serializers.ChoiceField(choices=User.USER_TYPE_CHOICES, default='customer')
    
    class Meta:
        model = User
        fields = ['id', 'username', 'email', 'password', 'password_confirm', 'user_type', 'company_name', 'phone']
        extra_kwargs = {
            'email': {'required': True},
        }
    
    def validate(self, attrs):
        if attrs['password'] != attrs['password_confirm']:
            raise serializers.ValidationError({'password_confirm': 'Passwords do not match.'})
        
        # Customers must provide company_name
        if attrs.get('user_type', 'customer') == 'customer' and not attrs.get('company_name'):
            raise serializers.ValidationError({'company_name': 'Company name is required for customer accounts.'})
        
        return attrs
    
    def create(self, validated_data):
        validated_data.pop('password_confirm')
        user_type = validated_data.get('user_type', 'customer')
        
        # Customers are inactive by default until approved by admin
        # Carriers and admins are active immediately (created by admin)
        if user_type == 'customer':
            validated_data['is_active'] = False
            validated_data['is_approved'] = False
        else:
            validated_data['is_approved'] = True
        
        user = User.objects.create_user(**validated_data)
        return user


class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ['id', 'username', 'email', 'user_type', 'company_name', 'phone', 'is_active', 'is_approved']
        read_only_fields = ['id', 'username', 'user_type', 'is_active', 'is_approved']


class UserApprovalSerializer(serializers.Serializer):
    """Serializer for approving or rejecting a user account."""
    action = serializers.ChoiceField(choices=['approve', 'reject'])
    rejection_reason = serializers.CharField(required=False, allow_blank=True)
    
    def validate(self, attrs):
        if attrs['action'] == 'reject' and not attrs.get('rejection_reason'):
            raise serializers.ValidationError({'rejection_reason': 'Rejection reason is required when rejecting an account.'})
        return attrs


class PendingUserSerializer(serializers.ModelSerializer):
    """Serializer for listing pending user approvals."""
    class Meta:
        model = User
        fields = ['id', 'username', 'email', 'company_name', 'phone', 'date_joined']
        read_only_fields = fields

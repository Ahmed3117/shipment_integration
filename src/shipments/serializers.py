from rest_framework import serializers
from datetime import datetime, timedelta
from decimal import Decimal
from .models import Address, ServiceType, Shipment, TrackingEvent, Webhook
from accounts.models import Company


class CompanySerializer(serializers.ModelSerializer):
    """Minimal serializer for Company information in responses."""
    class Meta:
        model = Company
        fields = ['id', 'name', 'email', 'phone', 'address']


class AddressSerializer(serializers.ModelSerializer):
    class Meta:
        model = Address
        fields = ['id', 'name', 'street', 'city', 'state', 'zip_code', 'country', 'phone']
    
    def validate_phone(self, value):
        # Remove non-digit characters for validation
        digits = ''.join(filter(str.isdigit, value))
        if len(digits) < 10:
            raise serializers.ValidationError('Invalid phone number. Must have at least 10 digits.')
        return value
    
    def validate_zip_code(self, value):
        if not value or len(value) < 3:
            raise serializers.ValidationError('Invalid zip code. Must have at least 3 characters.')
        return value
    
    def validate_city(self, value):
        if not value or len(value.strip()) < 2:
            raise serializers.ValidationError('Invalid city name.')
        return value.strip()
    
    def validate_state(self, value):
        if not value or len(value.strip()) < 2:
            raise serializers.ValidationError('Invalid state name.')
        return value.strip()
    
    def validate_street(self, value):
        if not value or len(value.strip()) < 5:
            raise serializers.ValidationError('Invalid street address. Must have at least 5 characters.')
        return value.strip()
    
    def validate_name(self, value):
        if not value or len(value.strip()) < 2:
            raise serializers.ValidationError('Invalid name. Must have at least 2 characters.')
        return value.strip()


class ServiceTypeSerializer(serializers.ModelSerializer):
    """Serializer for public service type listing."""
    class Meta:
        model = ServiceType
        fields = ['id', 'name', 'code', 'base_rate', 'rate_per_kg', 'estimated_days_min', 'estimated_days_max']


class ServiceTypeAdminSerializer(serializers.ModelSerializer):
    """Serializer for admin service type management (full CRUD)."""
    company_id = serializers.IntegerField(required=True, write_only=True)
    
    class Meta:
        model = ServiceType
        fields = ['id', 'name', 'code', 'base_rate', 'rate_per_kg', 'estimated_days_min', 'estimated_days_max', 'is_active', 'company_id']
    
    def validate_code(self, value):
        """Ensure code is lowercase and alphanumeric with underscores only."""
        import re
        if not re.match(r'^[a-z0-9_]+$', value.lower()):
            raise serializers.ValidationError('Code must contain only lowercase letters, numbers, and underscores.')
        return value.lower()
    
    def validate_company_id(self, value):
        """Validate that company exists."""
        try:
            Company.objects.get(id=value)
        except Company.DoesNotExist:
            raise serializers.ValidationError('Company not found.')
        return value
    
    def validate(self, data):
        """Ensure min days <= max days."""
        min_days = data.get('estimated_days_min')
        max_days = data.get('estimated_days_max')
        if min_days and max_days and min_days > max_days:
            raise serializers.ValidationError({
                'estimated_days_min': 'Minimum days cannot be greater than maximum days.'
            })
        return data
    
    def create(self, validated_data):
        company_id = validated_data.pop('company_id')
        validated_data['company'] = Company.objects.get(id=company_id)
        return super().create(validated_data)
    
    def update(self, instance, validated_data):
        company_id = validated_data.pop('company_id', None)
        if company_id is not None:
            validated_data['company'] = Company.objects.get(id=company_id)
        return super().update(instance, validated_data)


# --- Rate Calculation Serializers ---
class RateCalculationRequestSerializer(serializers.Serializer):
    origin_city = serializers.CharField(max_length=100)
    origin_state = serializers.CharField(max_length=100)
    origin_zip_code = serializers.CharField(max_length=20)
    origin_country = serializers.CharField(max_length=100, default='USA')
    
    destination_city = serializers.CharField(max_length=100)
    destination_state = serializers.CharField(max_length=100)
    destination_zip_code = serializers.CharField(max_length=20)
    destination_country = serializers.CharField(max_length=100, default='USA')
    
    weight = serializers.DecimalField(max_digits=10, decimal_places=2, min_value=Decimal('0.01'))
    length = serializers.DecimalField(max_digits=10, decimal_places=2, min_value=Decimal('0.01'))
    width = serializers.DecimalField(max_digits=10, decimal_places=2, min_value=Decimal('0.01'))
    height = serializers.DecimalField(max_digits=10, decimal_places=2, min_value=Decimal('0.01'))


class RateOptionSerializer(serializers.Serializer):
    service_id = serializers.IntegerField()
    service_name = serializers.CharField()
    service_code = serializers.CharField()
    estimated_cost = serializers.DecimalField(max_digits=10, decimal_places=2)
    estimated_delivery_date_min = serializers.DateField()
    estimated_delivery_date_max = serializers.DateField()


# --- Shipment Serializers ---
class ShipmentCreateSerializer(serializers.ModelSerializer):
    sender_address = AddressSerializer(required=False, allow_null=True)
    receiver_address = AddressSerializer()
    
    class Meta:
        model = Shipment
        fields = [
            'reference_number', 'sender_address', 'receiver_address',
            'weight', 'length', 'width', 'height', 'content_description',
            'service_type'
        ]
    
    def validate_weight(self, value):
        if value <= 0:
            raise serializers.ValidationError('Weight must be greater than 0.')
        if value > 1000:
            raise serializers.ValidationError('Weight cannot exceed 1000 kg.')
        return value
    
    def validate(self, attrs):
        # Validate dimensions
        for field in ['length', 'width', 'height']:
            if attrs.get(field, 0) <= 0:
                raise serializers.ValidationError({field: f'{field.capitalize()} must be greater than 0.'})
        return attrs
    
    def create(self, validated_data):
        sender_data = validated_data.pop('sender_address', None)
        receiver_data = validated_data.pop('receiver_address')
        
        sender = None
        if sender_data:
            sender = Address.objects.create(**sender_data)
        
        receiver = Address.objects.create(**receiver_data)
        
        service_type = validated_data['service_type']
        weight = validated_data['weight']
        
        # Calculate cost
        estimated_cost = service_type.base_rate + (service_type.rate_per_kg * weight)
        
        # Calculate estimated delivery date
        from datetime import date, timedelta
        estimated_delivery_date = date.today() + timedelta(days=service_type.estimated_days_max)
        
        shipment = Shipment.objects.create(
            sender_address=sender,
            receiver_address=receiver,
            estimated_cost=estimated_cost,
            estimated_delivery_date=estimated_delivery_date,
            status='created',
            label_url=f'/api/shipments/{{shipment_id}}/label/',
            **validated_data
        )
        
        # Create initial tracking event
        location = f"{sender.city}, {sender.state}" if sender else None
        TrackingEvent.objects.create(
            shipment=shipment,
            status='created',
            description='Shipment created successfully.',
            location=location
        )
        
        return shipment


class ShipmentListSerializer(serializers.ModelSerializer):
    sender_address = AddressSerializer(read_only=True)
    receiver_address = AddressSerializer(read_only=True)
    service_type = ServiceTypeSerializer(read_only=True)
    company = CompanySerializer(read_only=True)
    
    class Meta:
        model = Shipment
        fields = [
            'id', 'tracking_number', 'reference_number', 'status', 'company',
            'sender_address', 'receiver_address',
            'weight', 'length', 'width', 'height', 'content_description',
            'service_type', 'estimated_cost', 'estimated_delivery_date',
            'label_url', 'created_at', 'updated_at'
        ]


class ShipmentDetailSerializer(serializers.ModelSerializer):
    sender_address = AddressSerializer(read_only=True)
    receiver_address = AddressSerializer(read_only=True)
    service_type = ServiceTypeSerializer(read_only=True)
    company = CompanySerializer(read_only=True)
    
    class Meta:
        model = Shipment
        fields = [
            'id', 'tracking_number', 'reference_number', 'status', 'company',
            'sender_address', 'receiver_address',
            'weight', 'length', 'width', 'height', 'content_description',
            'service_type', 'estimated_cost', 'estimated_delivery_date',
            'label_url', 'created_at', 'updated_at'
        ]


# --- Tracking Serializers ---
class TrackingEventSerializer(serializers.ModelSerializer):
    class Meta:
        model = TrackingEvent
        fields = ['id', 'status', 'description', 'location', 'timestamp']


class TrackingResponseSerializer(serializers.Serializer):
    tracking_number = serializers.CharField()
    current_status = serializers.CharField()
    last_update = serializers.DateTimeField()
    reference_number = serializers.CharField()
    estimated_delivery_date = serializers.DateField()
    history = TrackingEventSerializer(many=True)


# --- Webhook Serializers ---
class WebhookSerializer(serializers.ModelSerializer):
    class Meta:
        model = Webhook
        fields = ['id', 'url', 'secret', 'is_active', 'created_at']
        read_only_fields = ['id', 'secret', 'created_at']
    
    def validate_url(self, value):
        if not value.startswith('https://'):
            raise serializers.ValidationError('Webhook URL must use HTTPS.')
        return value


class WebhookCreateSerializer(serializers.ModelSerializer):
    """Serializer for creating webhooks (secret is auto-generated)."""
    class Meta:
        model = Webhook
        fields = ['id', 'url', 'is_active', 'created_at']
        read_only_fields = ['id', 'created_at']
    
    def validate_url(self, value):
        if not value.startswith('https://'):
            raise serializers.ValidationError('Webhook URL must use HTTPS.')
        return value


class WebhookDetailSerializer(serializers.ModelSerializer):
    """Serializer showing webhook with secret (only on creation)."""
    class Meta:
        model = Webhook
        fields = ['id', 'url', 'secret', 'is_active', 'created_at']
        read_only_fields = fields


# --- Status Update Serializer ---
class ShipmentStatusUpdateSerializer(serializers.Serializer):
    STATUS_CHOICES = [
        'created', 'picked_up', 'in_transit',
        'out_for_delivery', 'delivered', 'cancelled', 'returned'
    ]
    
    status = serializers.ChoiceField(choices=STATUS_CHOICES)
    description = serializers.CharField(required=False, allow_blank=True)
    location = serializers.CharField(required=False, allow_blank=True, allow_null=True, default=None)


# --- Carrier Serializers ---
class CarrierShipmentListSerializer(serializers.ModelSerializer):
    """Serializer for carriers to view their assigned shipments."""
    sender_address = AddressSerializer(read_only=True)
    receiver_address = AddressSerializer(read_only=True)
    service_type = ServiceTypeSerializer(read_only=True)
    company_name = serializers.CharField(source='company.name', read_only=True)
    
    class Meta:
        model = Shipment
        fields = [
            'id', 'tracking_number', 'reference_number', 'status',
            'sender_address', 'receiver_address',
            'weight', 'content_description',
            'service_type', 'estimated_cost', 'estimated_delivery_date',
            'company_name', 'created_at'
        ]


class CarrierStatusUpdateSerializer(serializers.Serializer):
    """Serializer for carrier to update shipment status by scanning."""
    CARRIER_STATUS_CHOICES = [
        'picked_up', 'in_transit', 'out_for_delivery', 'delivered', 'returned'
    ]
    
    reference_number = serializers.CharField(max_length=100, required=False)
    tracking_number = serializers.CharField(max_length=50, required=False)
    status = serializers.ChoiceField(choices=CARRIER_STATUS_CHOICES)
    description = serializers.CharField(required=False, allow_blank=True)
    location = serializers.CharField(required=False, allow_blank=True, allow_null=True, default=None)
    
    def validate(self, attrs):
        if not attrs.get('reference_number') and not attrs.get('tracking_number'):
            raise serializers.ValidationError(
                'Either reference_number or tracking_number must be provided.'
            )
        return attrs


class TrackingEventDetailSerializer(serializers.ModelSerializer):
    """Tracking event with carrier info."""
    created_by_name = serializers.CharField(source='created_by.username', read_only=True, default=None)
    
    class Meta:
        model = TrackingEvent
        fields = ['id', 'status', 'description', 'location', 'created_by_name', 'timestamp']


class AssignCarrierSerializer(serializers.Serializer):
    """Serializer for assigning a carrier to a shipment."""
    carrier_id = serializers.IntegerField()
    
    def validate_carrier_id(self, value):
        from django.contrib.auth import get_user_model
        User = get_user_model()
        try:
            carrier = User.objects.get(id=value, user_type='carrier')
        except User.DoesNotExist:
            raise serializers.ValidationError('Carrier not found or user is not a carrier.')
        return value


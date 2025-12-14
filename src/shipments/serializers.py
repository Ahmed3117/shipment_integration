from rest_framework import serializers
from datetime import datetime, timedelta
from .models import Address, ServiceType, Shipment, TrackingEvent, Webhook


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
            raise serializers.ValidationError('Zip code not found.')
        return value


class ServiceTypeSerializer(serializers.ModelSerializer):
    class Meta:
        model = ServiceType
        fields = ['id', 'name', 'code', 'base_rate', 'rate_per_kg', 'estimated_days_min', 'estimated_days_max']


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
    
    weight = serializers.DecimalField(max_digits=10, decimal_places=2, min_value=0.01)
    length = serializers.DecimalField(max_digits=10, decimal_places=2, min_value=0.01)
    width = serializers.DecimalField(max_digits=10, decimal_places=2, min_value=0.01)
    height = serializers.DecimalField(max_digits=10, decimal_places=2, min_value=0.01)


class RateOptionSerializer(serializers.Serializer):
    service_id = serializers.IntegerField()
    service_name = serializers.CharField()
    service_code = serializers.CharField()
    estimated_cost = serializers.DecimalField(max_digits=10, decimal_places=2)
    estimated_delivery_date_min = serializers.DateField()
    estimated_delivery_date_max = serializers.DateField()


# --- Shipment Serializers ---
class ShipmentCreateSerializer(serializers.ModelSerializer):
    sender_address = AddressSerializer()
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
        sender_data = validated_data.pop('sender_address')
        receiver_data = validated_data.pop('receiver_address')
        
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
            status='confirmed',
            label_url=f'/api/shipments/{{shipment_id}}/label/',
            **validated_data
        )
        
        # Create initial tracking event
        TrackingEvent.objects.create(
            shipment=shipment,
            status='confirmed',
            description='Shipment created and confirmed.',
            location=f"{sender.city}, {sender.state}"
        )
        
        return shipment


class ShipmentListSerializer(serializers.ModelSerializer):
    service_type = ServiceTypeSerializer(read_only=True)
    
    class Meta:
        model = Shipment
        fields = [
            'id', 'tracking_number', 'reference_number', 'status',
            'service_type', 'estimated_cost', 'created_at'
        ]


class ShipmentDetailSerializer(serializers.ModelSerializer):
    sender_address = AddressSerializer(read_only=True)
    receiver_address = AddressSerializer(read_only=True)
    service_type = ServiceTypeSerializer(read_only=True)
    
    class Meta:
        model = Shipment
        fields = [
            'id', 'tracking_number', 'reference_number',
            'sender_address', 'receiver_address',
            'weight', 'length', 'width', 'height', 'content_description',
            'service_type', 'estimated_cost', 'estimated_delivery_date',
            'status', 'label_url', 'created_at', 'updated_at'
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
        fields = ['id', 'url', 'event', 'is_active', 'secret', 'created_at']
        read_only_fields = ['id', 'created_at']
        extra_kwargs = {
            'secret': {'write_only': True, 'required': False},
        }
    
    def validate_url(self, value):
        if not value.startswith('https://'):
            raise serializers.ValidationError('Webhook URL must use HTTPS.')
        return value


# --- Address Validation Serializer ---
class AddressValidationSerializer(serializers.Serializer):
    street = serializers.CharField(max_length=500, required=False, allow_blank=True)
    city = serializers.CharField(max_length=100)
    state = serializers.CharField(max_length=100)
    zip_code = serializers.CharField(max_length=20)
    country = serializers.CharField(max_length=100, default='USA')


class AddressValidationResponseSerializer(serializers.Serializer):
    is_valid = serializers.BooleanField()
    message = serializers.CharField()
    suggested_address = AddressSerializer(required=False, allow_null=True)


# --- Status Update Serializer ---
class ShipmentStatusUpdateSerializer(serializers.Serializer):
    STATUS_CHOICES = [
        'pending', 'confirmed', 'picked_up', 'in_transit',
        'out_for_delivery', 'delivered', 'cancelled', 'returned'
    ]
    
    status = serializers.ChoiceField(choices=STATUS_CHOICES)
    description = serializers.CharField(required=False, allow_blank=True)
    location = serializers.CharField(required=False, allow_blank=True, default='')

from rest_framework import serializers
from django.contrib.auth import get_user_model
from .models import SavedAddress

User = get_user_model()


class UserSerializer(serializers.ModelSerializer):
    """
    Serializer for customer profile view and updates.
    """

    class Meta:
        model = User
        fields = (
            'id',
            'email',
            'first_name',
            'last_name',
            'phone',
            'date_joined',
            'created_at',
            'updated_at',
        )
        read_only_fields = ('id', 'email', 'date_joined', 'created_at', 'updated_at')


class GoogleAuthSerializer(serializers.Serializer):
    """
    Serializer validating incoming Google OAuth payload.
    Accepts id_token, token, or code.
    """

    id_token = serializers.CharField(required=False, allow_blank=True)
    token = serializers.CharField(required=False, allow_blank=True)
    code = serializers.CharField(required=False, allow_blank=True)
    email = serializers.EmailField(required=False, allow_blank=True)
    name = serializers.CharField(required=False, allow_blank=True)

    def validate(self, attrs):
        token = attrs.get('id_token') or attrs.get('token') or attrs.get('code')
        if not token:
            raise serializers.ValidationError(
                "Either 'id_token', 'token', or 'code' must be provided."
            )
        return attrs


class SavedAddressSerializer(serializers.ModelSerializer):
    """
    Dual-compatibility serializer for customer saved delivery addresses.
    Accepts both frontend field names (houseFlat, streetArea, fullName)
    and backend model names (address_line1, address_line2, recipient_name).
    Enforces maximum address limits per user.
    """

    # Frontend alias fields (write-optional, mapped in to_internal_value)
    houseFlat = serializers.CharField(write_only=True, required=False)
    streetArea = serializers.CharField(write_only=True, required=False, allow_blank=True)
    fullName = serializers.CharField(write_only=True, required=False)

    class Meta:
        model = SavedAddress
        fields = (
            'id',
            'recipient_name',
            'phone',
            'address_line1',
            'address_line2',
            'landmark',
            'city',
            'state',
            'pincode',
            'country',
            'label',
            'is_default',
            'created_at',
            'updated_at',
            # Aliases for input
            'houseFlat',
            'streetArea',
            'fullName',
        )
        read_only_fields = ('id', 'created_at', 'updated_at')

    def to_internal_value(self, data):
        # Mutate copy to handle dual-key alias mappings
        mutable_data = data.copy() if hasattr(data, 'copy') else dict(data)

        if 'houseFlat' in mutable_data and not mutable_data.get('address_line1'):
            mutable_data['address_line1'] = mutable_data['houseFlat']
        if 'streetArea' in mutable_data and not mutable_data.get('address_line2'):
            mutable_data['address_line2'] = mutable_data['streetArea']
        if 'fullName' in mutable_data and not mutable_data.get('recipient_name'):
            mutable_data['recipient_name'] = mutable_data['fullName']

        return super().to_internal_value(mutable_data)

    def create(self, validated_data):
        validated_data.pop('houseFlat', None)
        validated_data.pop('streetArea', None)
        validated_data.pop('fullName', None)
        return super().create(validated_data)

    def update(self, instance, validated_data):
        validated_data.pop('houseFlat', None)
        validated_data.pop('streetArea', None)
        validated_data.pop('fullName', None)
        return super().update(instance, validated_data)

    def to_representation(self, instance):
        data = super().to_representation(instance)
        # Expose frontend aliases in response for seamless client deserialization
        data['houseFlat'] = instance.address_line1
        data['streetArea'] = instance.address_line2
        data['fullName'] = instance.recipient_name
        return data

    def validate(self, attrs):
        request = self.context.get('request')
        user = getattr(request, 'user', None)

        # Enforce maximum address limit (default: 3 saved addresses per customer)
        if self.instance is None and user and user.is_authenticated:
            max_allowed = 3
            if SavedAddress.objects.filter(user=user).count() >= max_allowed:
                raise serializers.ValidationError(
                    f"You have reached the maximum allowed limit of {max_allowed} saved addresses."
                )
        return attrs

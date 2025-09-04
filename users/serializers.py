from rest_framework import serializers
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer
from django.contrib.auth.password_validation import validate_password
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError

User = get_user_model()


class UserRegistrationSerializer(serializers.ModelSerializer):
    """
    Serializer for user registration
    """
    password = serializers.CharField(
        write_only=True,
        min_length=8,
        style={'input_type': 'password'}
    )
    password_confirm = serializers.CharField(
        write_only=True,
        style={'input_type': 'password'}
    )

    class Meta:
        model = User
        fields = [
            'email', 'username', 'first_name', 'last_name', 
            'password', 'password_confirm', 'phone',
            'address_line_1', 'address_line_2', 'city', 
            'state', 'postal_code', 'country', 'date_of_birth'
        ]
        extra_kwargs = {
            'email': {'required': True},
            'first_name': {'required': True},
            'last_name': {'required': True},
        }

    def validate_email(self, value):
        """Validate email is unique"""
        if User.objects.filter(email=value).exists():
            raise serializers.ValidationError("A user with this email already exists.")
        return value

    def validate_username(self, value):
        """Validate username is unique"""
        if User.objects.filter(username=value).exists():
            raise serializers.ValidationError("A user with this username already exists.")
        return value

    def validate_password(self, value):
        """Validate password strength"""
        try:
            validate_password(value)
        except ValidationError as e:
            raise serializers.ValidationError(e.messages)
        return value

    def validate(self, attrs):
        """Validate passwords match"""
        if attrs['password'] != attrs['password_confirm']:
            raise serializers.ValidationError(
                {"password_confirm": "Password fields didn't match."}
            )
        return attrs

    def create(self, validated_data):
        """Create new user"""
        validated_data.pop('password_confirm')
        password = validated_data.pop('password')
        
        user = User.objects.create(**validated_data)
        user.set_password(password)
        user.save()
        
        return user


class CustomTokenObtainPairSerializer(TokenObtainPairSerializer):
    """
    Custom token serializer to include user information in the response
    """
    username_field = 'email'

    def validate(self, attrs):
        data = super().validate(attrs)
        
        # Add user information to the token response
        data['user'] = {
            'id': self.user.id,
            'email': self.user.email,
            'username': self.user.username,
            'first_name': self.user.first_name,
            'last_name': self.user.last_name,
            'full_name': self.user.full_name,
            'is_staff': self.user.is_staff,
            'is_superuser': self.user.is_superuser,
        }
        
        return data

    @classmethod
    def get_token(cls, user):
        token = super().get_token(user)
        
        # Add custom claims to token
        token['email'] = user.email
        token['username'] = user.username
        token['full_name'] = user.full_name
        
        return token


class UserProfileSerializer(serializers.ModelSerializer):
    """
    Serializer for user profile view and updates
    """
    full_name = serializers.CharField(read_only=True)
    full_address = serializers.CharField(read_only=True)
    orders_count = serializers.SerializerMethodField()
    total_spent = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = [
            'id', 'email', 'username', 'first_name', 'last_name', 'full_name',
            'phone', 'address_line_1', 'address_line_2', 'city', 'state',
            'postal_code', 'country', 'full_address', 'date_of_birth',
            'profile_picture', 'date_joined', 'last_login', 'orders_count',
            'total_spent', 'is_active'
        ]
        read_only_fields = ['id', 'email', 'username', 'date_joined', 'last_login', 'is_active']

    def get_orders_count(self, obj):
        """Get total number of orders for the user"""
        return obj.get_orders_count()

    def get_total_spent(self, obj):
        """Get total amount spent by the user"""
        return obj.get_total_spent()


class UserProfileUpdateSerializer(serializers.ModelSerializer):
    """
    Serializer for updating user profile information
    """
    class Meta:
        model = User
        fields = [
            'first_name', 'last_name', 'phone', 'address_line_1', 
            'address_line_2', 'city', 'state', 'postal_code', 
            'country', 'date_of_birth', 'profile_picture'
        ]

    def validate_phone(self, value):
        """Validate phone number format"""
        if value and not value.replace('+', '').replace('-', '').replace(' ', '').isdigit():
            raise serializers.ValidationError("Enter a valid phone number.")
        return value


class ChangePasswordSerializer(serializers.Serializer):
    """
    Serializer for changing user password
    """
    old_password = serializers.CharField(required=True, style={'input_type': 'password'})
    new_password = serializers.CharField(required=True, style={'input_type': 'password'})
    new_password_confirm = serializers.CharField(required=True, style={'input_type': 'password'})

    def validate_old_password(self, value):
        """Validate old password is correct"""
        user = self.context['request'].user
        if not user.check_password(value):
            raise serializers.ValidationError("Old password is incorrect.")
        return value

    def validate_new_password(self, value):
        """Validate new password strength"""
        try:
            validate_password(value)
        except ValidationError as e:
            raise serializers.ValidationError(e.messages)
        return value

    def validate(self, attrs):
        """Validate new passwords match"""
        if attrs['new_password'] != attrs['new_password_confirm']:
            raise serializers.ValidationError(
                {"new_password_confirm": "New password fields didn't match."}
            )
        return attrs

    def save(self, **kwargs):
        """Change user password"""
        user = self.context['request'].user
        user.set_password(self.validated_data['new_password'])
        user.save()
        return user


class UserListSerializer(serializers.ModelSerializer):
    """
    Serializer for listing users (admin only)
    """
    full_name = serializers.CharField(read_only=True)
    orders_count = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = [
            'id', 'email', 'username', 'first_name', 'last_name', 'full_name',
            'phone', 'city', 'country', 'date_joined', 'last_login',
            'is_active', 'is_staff', 'orders_count'
        ]

    def get_orders_count(self, obj):
        """Get total number of orders for the user"""
        return obj.get_orders_count()


class PasswordResetRequestSerializer(serializers.Serializer):
    """
    Serializer for password reset request
    """
    email = serializers.EmailField(required=True)

    def validate_email(self, value):
        """Validate email exists"""
        if not User.objects.filter(email=value).exists():
            raise serializers.ValidationError("No user found with this email address.")
        return value


class PasswordResetConfirmSerializer(serializers.Serializer):
    """
    Serializer for password reset confirmation
    """
    token = serializers.CharField(required=True)
    new_password = serializers.CharField(required=True, style={'input_type': 'password'})
    new_password_confirm = serializers.CharField(required=True, style={'input_type': 'password'})

    def validate_new_password(self, value):
        """Validate new password strength"""
        try:
            validate_password(value)
        except ValidationError as e:
            raise serializers.ValidationError(e.messages)
        return value

    def validate(self, attrs):
        """Validate new passwords match"""
        if attrs['new_password'] != attrs['new_password_confirm']:
            raise serializers.ValidationError(
                {"new_password_confirm": "New password fields didn't match."}
            )
        return attrs 
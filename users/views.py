from rest_framework import generics, status, permissions
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView
from rest_framework_simplejwt.tokens import RefreshToken
from django.contrib.auth import get_user_model
from django.contrib.auth.tokens import default_token_generator
from django.utils.http import urlsafe_base64_encode, urlsafe_base64_decode
from django.utils.encoding import force_bytes, force_str
from django.core.mail import send_mail
from django.conf import settings
from drf_yasg.utils import swagger_auto_schema
from drf_yasg import openapi

from .serializers import (
    UserRegistrationSerializer,
    CustomTokenObtainPairSerializer,
    UserProfileSerializer,
    UserProfileUpdateSerializer,
    ChangePasswordSerializer,
    UserListSerializer,
    PasswordResetRequestSerializer,
    PasswordResetConfirmSerializer,
)

User = get_user_model()


class UserRegistrationView(generics.CreateAPIView):
    """
    Register a new user account
    """
    queryset = User.objects.all()
    serializer_class = UserRegistrationSerializer
    permission_classes = [permissions.AllowAny]

    @swagger_auto_schema(
        operation_description="Register a new user account",
        responses={
            201: openapi.Response(
                'User created successfully',
                UserProfileSerializer
            ),
            400: 'Bad Request'
        }
    )
    def post(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        if serializer.is_valid():
            user = serializer.save()
            
            # Generate tokens for immediate login
            refresh = RefreshToken.for_user(user)
            
            return Response({
                'message': 'User registered successfully',
                'user': UserProfileSerializer(user).data,
                'tokens': {
                    'refresh': str(refresh),
                    'access': str(refresh.access_token),
                }
            }, status=status.HTTP_201_CREATED)
        
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class CustomTokenObtainPairView(TokenObtainPairView):
    """
    Custom login view with user information
    """
    serializer_class = CustomTokenObtainPairSerializer

    @swagger_auto_schema(
        operation_description="Login with email and password to obtain JWT tokens",
        responses={
            200: openapi.Response(
                'Login successful',
                openapi.Schema(
                    type=openapi.TYPE_OBJECT,
                    properties={
                        'access': openapi.Schema(type=openapi.TYPE_STRING),
                        'refresh': openapi.Schema(type=openapi.TYPE_STRING),
                        'user': openapi.Schema(type=openapi.TYPE_OBJECT),
                    }
                )
            ),
            401: 'Invalid credentials'
        }
    )
    def post(self, request, *args, **kwargs):
        return super().post(request, *args, **kwargs)


class LogoutView(APIView):
    """
    Logout user by blacklisting the refresh token
    """
    permission_classes = [permissions.IsAuthenticated]

    @swagger_auto_schema(
        operation_description="Logout user by blacklisting refresh token",
        request_body=openapi.Schema(
            type=openapi.TYPE_OBJECT,
            properties={
                'refresh': openapi.Schema(type=openapi.TYPE_STRING)
            },
            required=['refresh']
        ),
        responses={
            200: 'Logout successful',
            400: 'Bad Request'
        }
    )
    def post(self, request):
        try:
            refresh_token = request.data["refresh"]
            token = RefreshToken(refresh_token)
            token.blacklist()
            return Response(
                {'message': 'Logout successful'}, 
                status=status.HTTP_200_OK
            )
        except Exception as e:
            return Response(
                {'error': 'Invalid token'}, 
                status=status.HTTP_400_BAD_REQUEST
            )


class UserProfileView(generics.RetrieveAPIView):
    """
    Get current user profile
    """
    serializer_class = UserProfileSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_object(self):
        return self.request.user

    @swagger_auto_schema(
        operation_description="Get current user profile information",
        responses={
            200: UserProfileSerializer,
            401: 'Unauthorized'
        }
    )
    def get(self, request, *args, **kwargs):
        return super().get(request, *args, **kwargs)


class UserProfileUpdateView(generics.UpdateAPIView):
    """
    Update current user profile
    """
    serializer_class = UserProfileUpdateSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_object(self):
        return self.request.user

    @swagger_auto_schema(
        operation_description="Update current user profile information",
        responses={
            200: UserProfileSerializer,
            400: 'Bad Request',
            401: 'Unauthorized'
        }
    )
    def patch(self, request, *args, **kwargs):
        response = super().patch(request, *args, **kwargs)
        if response.status_code == 200:
            # Return full profile data
            user = self.get_object()
            serializer = UserProfileSerializer(user)
            return Response({
                'message': 'Profile updated successfully',
                'user': serializer.data
            })
        return response


class ChangePasswordView(APIView):
    """
    Change user password
    """
    permission_classes = [permissions.IsAuthenticated]

    @swagger_auto_schema(
        operation_description="Change user password",
        request_body=ChangePasswordSerializer,
        responses={
            200: 'Password changed successfully',
            400: 'Bad Request',
            401: 'Unauthorized'
        }
    )
    def post(self, request):
        serializer = ChangePasswordSerializer(
            data=request.data, 
            context={'request': request}
        )
        
        if serializer.is_valid():
            serializer.save()
            return Response(
                {'message': 'Password changed successfully'}, 
                status=status.HTTP_200_OK
            )
        
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class UserListView(generics.ListAPIView):
    """
    List all users (Admin only)
    """
    queryset = User.objects.all().order_by('-date_joined')
    serializer_class = UserListSerializer
    permission_classes = [permissions.IsAdminUser]

    @swagger_auto_schema(
        operation_description="Get list of all users (Admin only)",
        responses={
            200: UserListSerializer(many=True),
            401: 'Unauthorized',
            403: 'Forbidden'
        }
    )
    def get(self, request, *args, **kwargs):
        return super().get(request, *args, **kwargs)


class UserDetailView(generics.RetrieveUpdateDestroyAPIView):
    """
    Get, update, or delete a specific user (Admin only)
    """
    queryset = User.objects.all()
    serializer_class = UserProfileSerializer
    permission_classes = [permissions.IsAdminUser]

    @swagger_auto_schema(
        operation_description="Get user details by ID (Admin only)",
        responses={
            200: UserProfileSerializer,
            401: 'Unauthorized',
            403: 'Forbidden',
            404: 'Not Found'
        }
    )
    def get(self, request, *args, **kwargs):
        return super().get(request, *args, **kwargs)

    @swagger_auto_schema(
        operation_description="Update user by ID (Admin only)",
        responses={
            200: UserProfileSerializer,
            400: 'Bad Request',
            401: 'Unauthorized',
            403: 'Forbidden',
            404: 'Not Found'
        }
    )
    def patch(self, request, *args, **kwargs):
        return super().patch(request, *args, **kwargs)

    @swagger_auto_schema(
        operation_description="Delete user by ID (Admin only)",
        responses={
            204: 'User deleted successfully',
            401: 'Unauthorized',
            403: 'Forbidden',
            404: 'Not Found'
        }
    )
    def delete(self, request, *args, **kwargs):
        return super().delete(request, *args, **kwargs)


class PasswordResetRequestView(APIView):
    """
    Request password reset
    """
    permission_classes = [permissions.AllowAny]

    @swagger_auto_schema(
        operation_description="Request password reset email",
        request_body=PasswordResetRequestSerializer,
        responses={
            200: 'Password reset email sent',
            400: 'Bad Request'
        }
    )
    def post(self, request):
        serializer = PasswordResetRequestSerializer(data=request.data)
        
        if serializer.is_valid():
            email = serializer.validated_data['email']
            user = User.objects.get(email=email)
            
            # Generate password reset token
            token = default_token_generator.make_token(user)
            uid = urlsafe_base64_encode(force_bytes(user.pk))
            
            # In a real application, you would send an email here
            # For now, we'll just return the token information
            reset_link = f"http://localhost:8000/api/auth/password-reset-confirm/{uid}/{token}/"
            
            # TODO: Send email with reset link
            # send_mail(
            #     'Password Reset Request',
            #     f'Click the link to reset your password: {reset_link}',
            #     settings.DEFAULT_FROM_EMAIL,
            #     [email],
            #     fail_silently=False,
            # )
            
            return Response({
                'message': 'Password reset email sent',
                'reset_link': reset_link  # Remove this in production
            }, status=status.HTTP_200_OK)
        
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class PasswordResetConfirmView(APIView):
    """
    Confirm password reset
    """
    permission_classes = [permissions.AllowAny]

    @swagger_auto_schema(
        operation_description="Confirm password reset with token",
        request_body=PasswordResetConfirmSerializer,
        responses={
            200: 'Password reset successful',
            400: 'Bad Request'
        }
    )
    def post(self, request, uidb64, token):
        try:
            uid = force_str(urlsafe_base64_decode(uidb64))
            user = User.objects.get(pk=uid)
        except (TypeError, ValueError, OverflowError, User.DoesNotExist):
            user = None

        if user is not None and default_token_generator.check_token(user, token):
            serializer = PasswordResetConfirmSerializer(data=request.data)
            
            if serializer.is_valid():
                user.set_password(serializer.validated_data['new_password'])
                user.save()
                
                return Response(
                    {'message': 'Password reset successful'}, 
                    status=status.HTTP_200_OK
                )
            
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        else:
            return Response(
                {'error': 'Invalid token'}, 
                status=status.HTTP_400_BAD_REQUEST
            )


@api_view(['GET'])
@permission_classes([permissions.IsAuthenticated])
def user_orders_view(request):
    """
    Get current user's orders
    """
    user = request.user
    orders = user.orders.all().order_by('-created_at')
    
    # We'll implement the OrderSerializer in the next phase
    from orders.serializers import OrderListSerializer
    serializer = OrderListSerializer(orders, many=True)
    
    return Response({
        'count': orders.count(),
        'orders': serializer.data
    })


@api_view(['POST'])
@permission_classes([permissions.AllowAny])
def check_email_availability(request):
    """
    Check if email is available for registration
    """
    email = request.data.get('email')
    if not email:
        return Response(
            {'error': 'Email is required'}, 
            status=status.HTTP_400_BAD_REQUEST
        )
    
    exists = User.objects.filter(email=email).exists()
    return Response({
        'email': email,
        'available': not exists
    })


@api_view(['POST'])
@permission_classes([permissions.AllowAny])
def check_username_availability(request):
    """
    Check if username is available for registration
    """
    username = request.data.get('username')
    if not username:
        return Response(
            {'error': 'Username is required'}, 
            status=status.HTTP_400_BAD_REQUEST
        )
    
    exists = User.objects.filter(username=username).exists()
    return Response({
        'username': username,
        'available': not exists
    })

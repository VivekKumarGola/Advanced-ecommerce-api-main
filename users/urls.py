from django.urls import path
from rest_framework_simplejwt.views import TokenRefreshView
from . import views

app_name = 'users'

urlpatterns = [
    # Authentication endpoints
    path('auth/register/', views.UserRegistrationView.as_view(), name='register'),
    path('auth/login/', views.CustomTokenObtainPairView.as_view(), name='login'),
    path('auth/logout/', views.LogoutView.as_view(), name='logout'),
    path('auth/token/refresh/', TokenRefreshView.as_view(), name='token_refresh'),
    
    # Password management
    path('auth/change-password/', views.ChangePasswordView.as_view(), name='change_password'),
    path('auth/password-reset/', views.PasswordResetRequestView.as_view(), name='password_reset'),
    path('auth/password-reset-confirm/<str:uidb64>/<str:token>/', 
         views.PasswordResetConfirmView.as_view(), name='password_reset_confirm'),
    
    # Profile management
    path('profile/', views.UserProfileView.as_view(), name='profile'),
    path('profile/update/', views.UserProfileUpdateView.as_view(), name='profile_update'),
    path('profile/orders/', views.user_orders_view, name='user_orders'),
    
    # Utility endpoints
    path('check-email/', views.check_email_availability, name='check_email'),
    path('check-username/', views.check_username_availability, name='check_username'),
    
    # Admin endpoints
    path('admin/users/', views.UserListView.as_view(), name='admin_user_list'),
    path('admin/users/<int:pk>/', views.UserDetailView.as_view(), name='admin_user_detail'),
] 
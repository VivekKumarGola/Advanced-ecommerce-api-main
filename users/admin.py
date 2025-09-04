from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.contrib.auth import get_user_model
from django.utils.html import format_html
from django.urls import reverse

User = get_user_model()


@admin.register(User)
class UserAdmin(BaseUserAdmin):
    """
    Enhanced User admin interface for e-commerce platform
    """
    list_display = [
        'email', 'username', 'full_name', 'phone', 'city', 
        'order_count', 'is_active', 'is_staff', 'date_joined'
    ]
    list_filter = [
        'is_active', 'is_staff', 'is_superuser', 
        'date_joined', 'last_login', 'country', 'city'
    ]
    search_fields = ['email', 'username', 'first_name', 'last_name', 'phone']
    ordering = ['-date_joined']
    readonly_fields = ['date_joined', 'last_login', 'order_count', 'full_name']
    list_per_page = 25
    
    fieldsets = BaseUserAdmin.fieldsets + (
        ('Profile Information', {
            'fields': (
                'phone', 'date_of_birth', 'profile_picture'
            )
        }),
        ('Address Information', {
            'fields': (
                'address_line_1', 'address_line_2', 'city', 
                'state', 'postal_code', 'country'
            )
        }),
        ('E-commerce Stats', {
            'fields': ('order_count',),
            'classes': ('collapse',)
        }),
    )
    
    add_fieldsets = BaseUserAdmin.add_fieldsets + (
        ('Profile Information', {
            'fields': (
                'email', 'first_name', 'last_name', 'phone'
            )
        }),
    )
    
    actions = ['activate_users', 'deactivate_users']
    
    def full_name(self, obj):
        """Display user's full name."""
        return f"{obj.first_name} {obj.last_name}".strip() or obj.username
    full_name.short_description = 'Full Name'
    
    def order_count(self, obj):
        """Display number of orders placed by user."""
        try:
            count = obj.orders.count()
            if count > 0:
                url = reverse('admin:orders_order_changelist') + f'?user__id__exact={obj.id}'
                return format_html('<a href="{}">{} orders</a>', url, count)
            return '0 orders'
        except:
            return '0 orders'
    order_count.short_description = 'Orders'
    order_count.admin_order_field = 'orders__count'
    
    # Admin actions
    def activate_users(self, request, queryset):
        """Activate selected users."""
        updated = queryset.update(is_active=True)
        self.message_user(request, f'{updated} users activated.')
    activate_users.short_description = 'Activate selected users'
    
    def deactivate_users(self, request, queryset):
        """Deactivate selected users."""
        updated = queryset.update(is_active=False)
        self.message_user(request, f'{updated} users deactivated.')
    deactivate_users.short_description = 'Deactivate selected users'

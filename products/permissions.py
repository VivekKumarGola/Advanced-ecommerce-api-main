from rest_framework import permissions


class IsAdminOrReadOnly(permissions.BasePermission):
    """
    Custom permission to only allow admin users to edit products/categories,
    but allow read-only access to authenticated users.
    """
    
    def has_permission(self, request, view):
        # Read permissions for any authenticated user
        if request.method in permissions.SAFE_METHODS:
            return request.user.is_authenticated
        
        # Write permissions only for admin users
        return request.user.is_authenticated and request.user.is_staff


class IsAdminUser(permissions.BasePermission):
    """
    Permission to only allow admin users to access the view.
    """
    
    def has_permission(self, request, view):
        return request.user.is_authenticated and request.user.is_staff


class IsOwnerOrAdmin(permissions.BasePermission):
    """
    Custom permission to only allow owners of an object or admins to edit it.
    """
    
    def has_object_permission(self, request, view, obj):
        # Read permissions for any authenticated user
        if request.method in permissions.SAFE_METHODS:
            return request.user.is_authenticated
        
        # Write permissions only for the owner or admin users
        return (
            request.user.is_authenticated and (
                request.user.is_staff or 
                obj.user == request.user
            )
        )


class CanManageProducts(permissions.BasePermission):
    """
    Permission for users who can manage products (admins and store managers).
    """
    
    def has_permission(self, request, view):
        if not request.user.is_authenticated:
            return False
        
        # Allow read access to all authenticated users
        if request.method in permissions.SAFE_METHODS:
            return True
        
        # Allow write access to staff and superusers
        return request.user.is_staff or request.user.is_superuser 
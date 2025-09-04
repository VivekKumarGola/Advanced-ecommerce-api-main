from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response
from rest_framework import status
from drf_yasg.utils import swagger_auto_schema
from drf_yasg import openapi
from django.db.models import Count, Q

from .permissions import IsAdminUser
from utils.cache import CacheManager, CacheStatsCollector


@api_view(['GET'])
@permission_classes([IsAdminUser])
@swagger_auto_schema(
    operation_description="Get cache statistics and performance metrics (Admin only)",
    responses={
        200: openapi.Schema(
            type=openapi.TYPE_OBJECT,
            properties={
                'cache_stats': openapi.Schema(type=openapi.TYPE_OBJECT),
                'memory_usage': openapi.Schema(type=openapi.TYPE_STRING),
                'hit_rate': openapi.Schema(type=openapi.TYPE_STRING),
                'connected_clients': openapi.Schema(type=openapi.TYPE_INTEGER),
            }
        )
    }
)
def cache_stats(request):
    """
    Get cache performance statistics
    """
    stats = CacheStatsCollector.get_cache_stats()
    
    return Response({
        'cache_stats': stats,
        'status': 'healthy' if stats.get('hit_rate', '0%') != 'N/A' else 'unavailable'
    })


@api_view(['POST'])
@permission_classes([IsAdminUser])
@swagger_auto_schema(
    operation_description="Clear specific cache groups (Admin only)",
    request_body=openapi.Schema(
        type=openapi.TYPE_OBJECT,
        properties={
            'groups': openapi.Schema(
                type=openapi.TYPE_ARRAY,
                items=openapi.Schema(type=openapi.TYPE_STRING),
                description="Cache groups to clear (product, category, order, user, search, stats)"
            )
        },
        required=['groups']
    ),
    responses={
        200: openapi.Schema(
            type=openapi.TYPE_OBJECT,
            properties={
                'message': openapi.Schema(type=openapi.TYPE_STRING),
                'cleared_groups': openapi.Schema(type=openapi.TYPE_ARRAY, items=openapi.Schema(type=openapi.TYPE_STRING)),
                'keys_deleted': openapi.Schema(type=openapi.TYPE_INTEGER),
            }
        ),
        400: 'Bad Request'
    }
)
def clear_cache(request):
    """
    Clear specific cache groups
    """
    groups = request.data.get('groups', [])
    
    if not groups:
        return Response(
            {'error': 'No cache groups specified'},
            status=status.HTTP_400_BAD_REQUEST
        )
    
    valid_groups = ['product', 'category', 'order', 'user', 'search', 'stats', 'api']
    invalid_groups = [g for g in groups if g not in valid_groups]
    
    if invalid_groups:
        return Response(
            {
                'error': f'Invalid cache groups: {invalid_groups}',
                'valid_groups': valid_groups
            },
            status=status.HTTP_400_BAD_REQUEST
        )
    
    total_deleted = 0
    cleared_groups = []
    
    for group in groups:
        deleted_count = CacheManager.invalidate_group(group)
        total_deleted += deleted_count
        cleared_groups.append(group)
    
    return Response({
        'message': f'Successfully cleared {len(cleared_groups)} cache groups',
        'cleared_groups': cleared_groups,
        'keys_deleted': total_deleted
    })


@api_view(['POST'])
@permission_classes([IsAdminUser])
@swagger_auto_schema(
    operation_description="Clear all cache data (Admin only)",
    responses={
        200: openapi.Schema(
            type=openapi.TYPE_OBJECT,
            properties={
                'message': openapi.Schema(type=openapi.TYPE_STRING),
                'status': openapi.Schema(type=openapi.TYPE_STRING),
            }
        )
    }
)
def flush_all_cache(request):
    """
    Clear all cache data (use with caution)
    """
    try:
        from django.core.cache import cache
        cache.clear()
        
        return Response({
            'message': 'All cache data has been cleared',
            'status': 'success'
        })
    except Exception as e:
        return Response({
            'message': f'Error clearing cache: {str(e)}',
            'status': 'error'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['GET'])
@permission_classes([IsAdminUser])
@swagger_auto_schema(
    operation_description="Warm up cache by pre-loading frequently accessed data (Admin only)",
    responses={
        200: openapi.Schema(
            type=openapi.TYPE_OBJECT,
            properties={
                'message': openapi.Schema(type=openapi.TYPE_STRING),
                'warmed_endpoints': openapi.Schema(type=openapi.TYPE_ARRAY, items=openapi.Schema(type=openapi.TYPE_STRING)),
            }
        )
    }
)
def warm_cache(request):
    """
    Pre-load frequently accessed data into cache
    """
    warmed_endpoints = []
    
    try:
        # Import here to avoid circular imports
        from .models import Category, Product
        from .serializers import CategoryListSerializer, ProductListSerializer
        from utils.cache import CacheKeys
        
        # Warm category list
        categories = Category.objects.filter(is_active=True).annotate(
            products_count=Count('products', filter=Q(products__is_active=True))
        ).order_by('name')
        category_serializer = CategoryListSerializer(categories, many=True)
        cache_key = CacheKeys.category_list()
        CacheManager.set(cache_key, category_serializer.data, 'long')
        warmed_endpoints.append('categories')
        
        # Warm featured products
        featured_products = Product.objects.filter(
            is_active=True, is_featured=True
        ).select_related('category').order_by('-created_at')[:20]
        
        if featured_products:
            product_serializer = ProductListSerializer(featured_products, many=True)
            cache_key = CacheKeys.product_list(is_featured=True)
            CacheManager.set(cache_key, product_serializer.data, 'medium')
            warmed_endpoints.append('featured_products')
        
        # Warm recent products (first page)
        recent_products = Product.objects.filter(
            is_active=True
        ).select_related('category').order_by('-created_at')[:20]
        
        if recent_products:
            product_serializer = ProductListSerializer(recent_products, many=True)
            cache_key = CacheKeys.product_list(page=1)
            CacheManager.set(cache_key, product_serializer.data, 'medium')
            warmed_endpoints.append('recent_products')
        
        return Response({
            'message': f'Cache warmed successfully for {len(warmed_endpoints)} endpoints',
            'warmed_endpoints': warmed_endpoints
        })
        
    except Exception as e:
        return Response({
            'message': f'Error warming cache: {str(e)}',
            'warmed_endpoints': warmed_endpoints
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR) 
from rest_framework import serializers
from django.core.cache import cache
from .models import Category, Product, ProductImage


class CategoryListSerializer(serializers.ModelSerializer):
    """
    Serializer for listing categories
    """
    products_count = serializers.SerializerMethodField()
    
    class Meta:
        model = Category
        fields = [
            'id', 'name', 'description', 'slug', 'image', 
            'is_active', 'products_count', 'created_at', 'updated_at'
        ]
    
    def get_products_count(self, obj):
        """Get count of active products in this category"""
        return obj.get_products_count()


class CategoryDetailSerializer(serializers.ModelSerializer):
    """
    Serializer for detailed category view
    """
    products_count = serializers.SerializerMethodField()
    
    class Meta:
        model = Category
        fields = [
            'id', 'name', 'description', 'slug', 'image', 'is_active',
            'meta_title', 'meta_description', 'products_count',
            'created_at', 'updated_at'
        ]
    
    def get_products_count(self, obj):
        """Get count of active products in this category"""
        return obj.get_products_count()


class CategoryCreateUpdateSerializer(serializers.ModelSerializer):
    """
    Serializer for creating and updating categories
    """
    class Meta:
        model = Category
        fields = [
            'name', 'description', 'image', 'is_active',
            'meta_title', 'meta_description'
        ]
    
    def validate_name(self, value):
        """Validate category name is unique"""
        instance = getattr(self, 'instance', None)
        if Category.objects.filter(name=value).exclude(pk=instance.pk if instance else None).exists():
            raise serializers.ValidationError("A category with this name already exists.")
        return value


class ProductImageSerializer(serializers.ModelSerializer):
    """
    Serializer for product images
    """
    class Meta:
        model = ProductImage
        fields = ['id', 'image', 'alt_text', 'is_primary', 'order']


class ProductListSerializer(serializers.ModelSerializer):
    """
    Serializer for listing products with basic information
    """
    category_name = serializers.CharField(source='category.name', read_only=True)
    stock_status = serializers.CharField(read_only=True)
    
    class Meta:
        model = Product
        fields = [
            'id', 'name', 'slug', 'price', 'stock', 'stock_status',
            'category', 'category_name', 'image', 'is_active', 
            'is_featured', 'created_at', 'updated_at'
        ]


class ProductDetailSerializer(serializers.ModelSerializer):
    """
    Serializer for detailed product view
    """
    category = CategoryListSerializer(read_only=True)
    stock_status = serializers.CharField(read_only=True)
    additional_images = ProductImageSerializer(many=True, read_only=True)
    discount_percentage = serializers.SerializerMethodField()
    
    class Meta:
        model = Product
        fields = [
            'id', 'name', 'description', 'slug', 'price', 'cost_price',
            'stock', 'low_stock_threshold', 'stock_status', 'category',
            'sku', 'weight', 'dimensions', 'image', 'image_2', 'image_3',
            'additional_images', 'is_active', 'is_featured', 'meta_title',
            'meta_description', 'discount_percentage', 'created_at', 'updated_at'
        ]
    
    def get_discount_percentage(self, obj):
        """Get discount percentage"""
        return obj.get_discount_percentage()


class ProductCreateUpdateSerializer(serializers.ModelSerializer):
    """
    Serializer for creating and updating products
    """
    additional_images = ProductImageSerializer(many=True, required=False)
    
    class Meta:
        model = Product
        fields = [
            'name', 'description', 'price', 'cost_price', 'stock',
            'low_stock_threshold', 'category', 'weight', 'dimensions',
            'image', 'image_2', 'image_3', 'is_active', 'is_featured',
            'meta_title', 'meta_description', 'additional_images'
        ]
    
    def validate_price(self, value):
        """Validate price is positive"""
        if value <= 0:
            raise serializers.ValidationError("Price must be greater than zero.")
        return value
    
    def validate_cost_price(self, value):
        """Validate cost price if provided"""
        if value is not None and value < 0:
            raise serializers.ValidationError("Cost price cannot be negative.")
        return value
    
    def validate_stock(self, value):
        """Validate stock is not negative"""
        if value < 0:
            raise serializers.ValidationError("Stock cannot be negative.")
        return value
    
    def validate_name(self, value):
        """Validate product name is unique"""
        instance = getattr(self, 'instance', None)
        if Product.objects.filter(name=value).exclude(pk=instance.pk if instance else None).exists():
            raise serializers.ValidationError("A product with this name already exists.")
        return value
    
    def create(self, validated_data):
        """Create product with additional images"""
        additional_images_data = validated_data.pop('additional_images', [])
        product = Product.objects.create(**validated_data)
        
        # Create additional images
        for image_data in additional_images_data:
            ProductImage.objects.create(product=product, **image_data)
        
        # Invalidate cache
        self._invalidate_cache()
        
        return product
    
    def update(self, instance, validated_data):
        """Update product with additional images"""
        additional_images_data = validated_data.pop('additional_images', None)
        
        # Update product fields
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()
        
        # Update additional images if provided
        if additional_images_data is not None:
            # Delete existing additional images
            instance.additional_images.all().delete()
            
            # Create new additional images
            for image_data in additional_images_data:
                ProductImage.objects.create(product=instance, **image_data)
        
        # Invalidate cache
        self._invalidate_cache()
        
        return instance
    
    def _invalidate_cache(self):
        """Invalidate related cache keys"""
        cache_keys = [
            'products_list',
            'categories_list',
            'featured_products',
        ]
        cache.delete_many(cache_keys)


class ProductStockUpdateSerializer(serializers.ModelSerializer):
    """
    Serializer for updating product stock only
    """
    class Meta:
        model = Product
        fields = ['stock']
    
    def validate_stock(self, value):
        """Validate stock is not negative"""
        if value < 0:
            raise serializers.ValidationError("Stock cannot be negative.")
        return value
    
    def update(self, instance, validated_data):
        """Update stock and invalidate cache"""
        instance.stock = validated_data['stock']
        instance.save(update_fields=['stock', 'updated_at'])
        
        # Invalidate cache
        cache.delete_many(['products_list', 'featured_products'])
        
        return instance


class ProductBulkCreateSerializer(serializers.Serializer):
    """
    Serializer for bulk product creation
    """
    products = ProductCreateUpdateSerializer(many=True)
    
    def create(self, validated_data):
        """Create multiple products"""
        products_data = validated_data['products']
        created_products = []
        
        for product_data in products_data:
            additional_images_data = product_data.pop('additional_images', [])
            product = Product.objects.create(**product_data)
            
            # Create additional images
            for image_data in additional_images_data:
                ProductImage.objects.create(product=product, **image_data)
            
            created_products.append(product)
        
        # Invalidate cache
        cache.delete_many(['products_list', 'categories_list', 'featured_products'])
        
        return {'products': created_products}


class ProductSearchSerializer(serializers.Serializer):
    """
    Serializer for product search parameters
    """
    query = serializers.CharField(required=False, allow_blank=True)
    category = serializers.IntegerField(required=False)
    min_price = serializers.DecimalField(max_digits=10, decimal_places=2, required=False)
    max_price = serializers.DecimalField(max_digits=10, decimal_places=2, required=False)
    in_stock = serializers.BooleanField(required=False)
    is_featured = serializers.BooleanField(required=False)
    ordering = serializers.ChoiceField(
        choices=[
            'name', '-name', 'price', '-price', 'created_at', '-created_at',
            'stock', '-stock', 'category__name', '-category__name'
        ],
        required=False
    )
    
    def validate(self, attrs):
        """Validate search parameters"""
        min_price = attrs.get('min_price')
        max_price = attrs.get('max_price')
        
        if min_price and max_price and min_price > max_price:
            raise serializers.ValidationError(
                "Minimum price cannot be greater than maximum price."
            )
        
        return attrs 
"""
Main Django views for frontend pages and AJAX API endpoints.
"""

import json
import logging
from decimal import Decimal
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import login, logout, authenticate
from django.contrib.auth.decorators import login_required
from django.contrib.admin.views.decorators import staff_member_required
from django.contrib import messages
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods, require_POST
from django.core.paginator import Paginator
from django.db.models import Q
from django.db import transaction
from django.conf import settings
from rest_framework_simplejwt.tokens import RefreshToken
from products.models import Product, Category
from orders.models import Cart, CartItem, Order, OrderItem
from users.models import User
from utils.cache import CacheManager

logger = logging.getLogger(__name__)
cache_manager = CacheManager()


def home_view(request):
    """
    Home page view displaying featured products and categories.
    """
    try:
        # Get featured products (limit to 8)
        featured_products = Product.objects.filter(
            is_featured=True, 
            stock__gt=0
        ).select_related('category')[:8]
        
        # Get all categories with product counts
        categories = Category.objects.all()
        
        context = {
            'featured_products': featured_products,
            'categories': categories,
        }
        
        return render(request, 'shop/home.html', context)
        
    except Exception as e:
        logger.error(f"Error in home_view: {e}")
        messages.error(request, "An error occurred while loading the home page.")
        return render(request, 'shop/home.html', {'featured_products': [], 'categories': []})


def products_list_view(request):
    """
    Products listing page with filtering, sorting, and pagination.
    """
    try:
        # Get query parameters
        category_slug = request.GET.get('category', '')
        search_query = request.GET.get('search', '')
        price_range = request.GET.get('price_range', '')
        sort_by = request.GET.get('sort', '')
        per_page = int(request.GET.get('per_page', 10))
        
        # Base queryset
        products = Product.objects.select_related('category').filter(stock__gt=0)
        
        # Category filter
        current_category = None
        if category_slug:
            try:
                current_category = Category.objects.get(slug=category_slug)
                products = products.filter(category=current_category)
            except Category.DoesNotExist:
                pass
        
        # Search filter
        if search_query:
            products = products.filter(
                Q(name__icontains=search_query) | 
                Q(description__icontains=search_query)
            )
        
        # Price range filter
        if price_range:
            if price_range == '0-50':
                products = products.filter(price__lte=50)
            elif price_range == '50-100':
                products = products.filter(price__gte=50, price__lte=100)
            elif price_range == '100-200':
                products = products.filter(price__gte=100, price__lte=200)
            elif price_range == '200-500':
                products = products.filter(price__gte=200, price__lte=500)
            elif price_range == '500+':
                products = products.filter(price__gte=500)
        
        # Sorting
        if sort_by:
            if sort_by in ['name', '-name', 'price', '-price', 'created_at', '-created_at']:
                products = products.order_by(sort_by)
        else:
            products = products.order_by('-created_at')  # Default: newest first
        
        # Pagination
        paginator = Paginator(products, per_page)
        page_number = request.GET.get('page')
        page_obj = paginator.get_page(page_number)
        
        # Get all categories for sidebar
        categories = Category.objects.all()
        
        context = {
            'products': page_obj,
            'page_obj': page_obj,
            'categories': categories,
            'current_category': category_slug,
            'search_query': search_query,
            'price_range': price_range,
            'sort_by': sort_by,
            'items_per_page': per_page,
        }
        
        return render(request, 'shop/products.html', context)
        
    except Exception as e:
        logger.error(f"Error in products_list_view: {e}")
        messages.error(request, "An error occurred while loading products.")
        return render(request, 'shop/products.html', {'products': [], 'categories': []})


@login_required
def cart_view(request):
    """
    Shopping cart page view.
    """
    try:
        cart, created = Cart.objects.get_or_create(user=request.user)
        
        context = {
            'cart': cart,
        }
        
        return render(request, 'shop/cart.html', context)
        
    except Exception as e:
        logger.error(f"Error in cart_view: {e}")
        messages.error(request, "An error occurred while loading your cart.")
        return render(request, 'shop/cart.html', {'cart': None})


@login_required
def profile_view(request):
    """
    User profile page.
    """
    return render(request, 'users/profile.html', {'user': request.user})


@login_required
def user_orders_view(request):
    """
    User orders history page.
    """
    try:
        orders = Order.objects.filter(user=request.user).order_by('-created_at')
        
        context = {
            'orders': orders,
        }
        
        return render(request, 'orders/user_orders.html', context)
        
    except Exception as e:
        logger.error(f"Error in user_orders_view: {e}")
        messages.error(request, "An error occurred while loading your orders.")
        return render(request, 'orders/user_orders.html', {'orders': []})


def login_view(request):
    """
    User login page.
    """
    if request.method == 'POST':
        email = request.POST.get('email')
        password = request.POST.get('password')
        
        user = authenticate(request, username=email, password=password)
        if user:
            login(request, user)
            messages.success(request, 'Successfully logged in!')
            return redirect('home')
        else:
            messages.error(request, 'Invalid email or password.')
    
    return render(request, 'users/login.html')


def register_view(request):
    """
    User registration page.
    """
    if request.method == 'POST':
        email = request.POST.get('email')
        password = request.POST.get('password')
        first_name = request.POST.get('first_name')
        last_name = request.POST.get('last_name')
        
        try:
            if User.objects.filter(email=email).exists():
                messages.error(request, 'Email already exists.')
            else:
                user = User.objects.create_user(
                    username=email,
                    email=email,
                    password=password,
                    first_name=first_name,
                    last_name=last_name
                )
                login(request, user)
                messages.success(request, 'Registration successful!')
                return redirect('home')
        except Exception as e:
            logger.error(f"Error in registration: {e}")
            messages.error(request, 'Registration failed. Please try again.')
    
    return render(request, 'users/register.html')


def logout_view(request):
    """
    User logout.
    """
    logout(request)
    messages.success(request, 'Successfully logged out!')
    return redirect('home')


# AJAX API Endpoints
@require_http_methods(["GET"])
def api_cart_view(request):
    """
    AJAX endpoint to get cart information.
    """
    try:
        if not request.user.is_authenticated:
            return JsonResponse({'total_items': 0, 'total_amount': 0.0})
        
        cart, created = Cart.objects.get_or_create(user=request.user)
        
        return JsonResponse({
            'total_items': cart.total_items,
            'total_amount': float(cart.total_price),
            'items': [
                {
                    'id': item.id,
                    'product_id': item.product.id,
                    'product_name': item.product.name,
                    'quantity': item.quantity,
                    'price': float(item.product.price),
                    'subtotal': float(item.subtotal)
                }
                for item in cart.items.all()
            ]
        })
        
    except Exception as e:
        logger.error(f"Error in api_cart_view: {e}")
        return JsonResponse({'error': 'Failed to load cart'}, status=500)


@require_POST
@login_required
def api_cart_add(request):
    """
    AJAX endpoint to add item to cart.
    """
    try:
        data = json.loads(request.body)
        product_id = data.get('product_id')
        quantity = int(data.get('quantity', 1))
        
        product = get_object_or_404(Product, id=product_id)
        
        if product.stock < quantity:
            return JsonResponse({'error': 'Insufficient stock'}, status=400)
        
        cart, created = Cart.objects.get_or_create(user=request.user)
        cart_item, created = CartItem.objects.get_or_create(
            cart=cart,
            product=product,
            defaults={'quantity': quantity}
        )
        
        if not created:
            new_quantity = cart_item.quantity + quantity
            if product.stock < new_quantity:
                return JsonResponse({'error': 'Insufficient stock'}, status=400)
            cart_item.quantity = new_quantity
            cart_item.save()
        
        return JsonResponse({
            'success': True,
            'message': f'{product.name} added to cart',
            'cart_total_items': cart.total_items,
            'cart_total_amount': float(cart.total_price)
        })
        
    except Exception as e:
        logger.error(f"Error in api_cart_add: {e}")
        return JsonResponse({'error': 'Failed to add item to cart'}, status=500)


@require_POST
@login_required
def api_cart_update(request):
    """
    AJAX endpoint to update cart item quantity.
    """
    try:
        data = json.loads(request.body)
        item_id = data.get('item_id')
        quantity = int(data.get('quantity'))
        
        cart_item = get_object_or_404(CartItem, id=item_id, cart__user=request.user)
        cart = cart_item.cart  # Get cart reference before potentially deleting the item
        
        if quantity <= 0:
            cart_item.delete()
        else:
            if cart_item.product.stock < quantity:
                return JsonResponse({'error': 'Insufficient stock'}, status=400)
            cart_item.quantity = quantity
            cart_item.save()
        
        return JsonResponse({
            'success': True,
            'message': 'Cart updated successfully',
            'cart_total_items': cart.total_items,
            'cart_total_amount': float(cart.total_price)
        })
        
    except Exception as e:
        logger.error(f"Error in api_cart_update: {e}")
        return JsonResponse({'error': 'Failed to update cart'}, status=500)


@require_POST
@login_required
def api_cart_remove(request):
    """
    AJAX endpoint to remove item from cart.
    """
    try:
        data = json.loads(request.body)
        item_id = data.get('item_id')
        
        cart_item = get_object_or_404(CartItem, id=item_id, cart__user=request.user)
        cart = cart_item.cart
        cart_item.delete()
        
        return JsonResponse({
            'success': True,
            'message': 'Item removed from cart',
            'cart_total_items': cart.total_items,
            'cart_total_amount': float(cart.total_price)
        })
        
    except Exception as e:
        logger.error(f"Error in api_cart_remove: {e}")
        return JsonResponse({'error': 'Failed to remove item'}, status=500)


@require_POST
@login_required
def api_checkout(request):
    """
    AJAX endpoint to process checkout and create order.
    """
    try:
        data = json.loads(request.body)
        
        # Get user's cart
        cart = get_object_or_404(Cart, user=request.user)
        
        if not cart.items.exists():
            return JsonResponse({'error': 'Cart is empty'}, status=400)
        
        # Create order
        with transaction.atomic():
            order = Order.objects.create(
                user=request.user,
                subtotal=cart.total_price,
                total_price=cart.total_price,
                shipping_first_name=data.get('first_name', ''),
                shipping_last_name=data.get('last_name', ''),
                shipping_email=data.get('email', request.user.email),
                shipping_phone=data.get('phone', ''),
                shipping_address_line_1=data.get('address_line_1', ''),
                shipping_address_line_2=data.get('address_line_2', ''),
                shipping_city=data.get('city', ''),
                shipping_state=data.get('state', ''),
                shipping_postal_code=data.get('postal_code', ''),
                shipping_country=data.get('country', 'USA'),
                status='pending'
            )
            
            # Create order items and update stock
            for cart_item in cart.items.all():
                if cart_item.product.stock < cart_item.quantity:
                    return JsonResponse({
                        'error': f'Insufficient stock for {cart_item.product.name}'
                    }, status=400)
                
                OrderItem.objects.create(
                    order=order,
                    product=cart_item.product,
                    quantity=cart_item.quantity,
                    product_price=cart_item.product.price,
                    product_name=cart_item.product.name,
                    product_sku=getattr(cart_item.product, 'sku', f'SKU-{cart_item.product.id}')
                )
                
                # Update stock
                cart_item.product.stock -= cart_item.quantity
                cart_item.product.save()
            
            # Clear cart
            cart.items.all().delete()
        
        return JsonResponse({
            'success': True,
            'message': f'Order {order.order_number} placed successfully!',
            'order_id': order.id,
            'order_number': order.order_number,
            'redirect_url': '/orders/'
        })
        
    except Exception as e:
        logger.error(f"Error in api_checkout: {e}")
        return JsonResponse({'error': 'Checkout failed. Please try again.'}, status=500)


@staff_member_required
def admin_orders_view(request):
    """
    Admin orders management page.
    """
    try:
        orders = Order.objects.all().select_related('user').order_by('-created_at')
        
        context = {
            'orders': orders,
        }
        
        return render(request, 'admin/orders.html', context)
        
    except Exception as e:
        logger.error(f"Error in admin_orders_view: {e}")
        messages.error(request, "An error occurred while loading orders.")
        return render(request, 'admin/orders.html', {'orders': []})


@require_POST
@staff_member_required
def api_order_status_update(request):
    """
    AJAX endpoint for admin to update order status.
    """
    try:
        data = json.loads(request.body)
        order_id = data.get('order_id')
        new_status = data.get('status')
        
        order = get_object_or_404(Order, id=order_id)
        order.status = new_status
        order.save()
        
        return JsonResponse({
            'success': True,
            'message': f'Order {order.order_number} status updated to {order.get_status_display()}',
            'order_id': order.id,
            'order_number': order.order_number,
            'new_status': order.status,
            'new_status_display': order.get_status_display()
        })
        
    except Exception as e:
        logger.error(f"Error in api_order_status_update: {e}")
        return JsonResponse({'error': 'Failed to update order status'}, status=500) 
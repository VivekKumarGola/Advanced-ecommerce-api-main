E-commerce API (Advanced) with Redis Caching & Real-Time Notifications

Assignment Status: COMPLETE
A production-ready Django REST API for e-commerce featuring JWT authentication, product & order management, Redis caching, and WebSocket-based notifications.

    Assignment Compliance
✅ Authentication & User Management

JWT (SimpleJWT) with access & refresh tokens

Registration with validation (email, password)

Secure login & profile management (name, address, phone, email)

Order history for authenticated users

WebSocket JWT authentication

✅ Product & Inventory

Models: Category (name, description) & Product (name, description, price, stock, category)

Admin CRUD for categories/products

Stock auto-decrement on order

Extras: product images, SEO slugs

✅ Orders & Cart System

Add/update/remove cart items

Checkout with validation

Order lifecycle: Pending → Shipped → Delivered

Real-time order status notifications via WebSockets

✅ Performance & Caching

Redis-based caching with fallbacks

select_related + prefetch_related optimizations

Smart cache invalidation on product/stock changes

Multi-tier cache expiry (5 min – 24 hrs)

✅ Filtering & Pagination

10 products per page (requirement met)

Category, price range, and stock filters

Efficient for large datasets

✅ Notifications

Real-time updates via Django Channels

Per-user channels for orders

Admin alerts for new orders

✅ Infrastructure

Django 4.2 + DRF 3.14

PostgreSQL (production) / SQLite (dev)

Redis (caching + WebSocket layer)

Environment variables, logging, security best practices

🚀 Features Overview
🔐 Authentication

JWT token system (login, refresh)

Email-based signup

Profile & order history endpoints

Admin dashboard for user management

📦 Products

Categories & hierarchical organization

Product catalog with images & descriptions

Real-time stock updates

Advanced search, filtering & SEO-friendly URLs

🛍️ Orders

Cart with quantity management

Checkout & validation

Full order tracking + admin dashboard

Invoice & receipt generation

⚡ Performance

Redis caching with invalidation

Optimized DB queries

CDN-ready static/media

Configurable pagination

🔔 Real-Time

WebSocket notifications per user

Order status push updates

Admin alerts for incoming orders

🛠️ Tech Stack
Layer	Technology	Purpose
Backend	Django + DRF	Core API
Auth	SimpleJWT	Token-based authentication
Database	PostgreSQL (prod), SQLite	Persistence
Caching	Redis + django-redis	Performance
Real-time	Django Channels + WebSocket	Notifications
Docs	drf-yasg (Swagger/OpenAPI)	Interactive API docs
Frontend	HTML5, Bootstrap 5, JS	Responsive UI
📋 Setup Guide
Prerequisites

Python 3.11+

Django 4.2+

Redis server

PostgreSQL

Quick Start
git clone <repository-url>
cd enlog_assignment
python -m venv venv
source venv/bin/activate   # (or venv\Scripts\activate on Windows)
pip install -r requirements.txt
python manage.py migrate
python manage.py createsuperuser
python manage.py runserver


Access Points:

API Root → http://127.0.0.1:8000/

Admin Panel → /admin/

Swagger Docs → /swagger/

ReDoc → /redoc/

🔧 API Reference
🔐 Auth

POST /api/users/auth/register/ → Register

POST /api/users/auth/login/ → Login

POST /api/users/auth/token/refresh/ → Refresh token

GET/PUT /api/users/profile/ → Get/update profile

📦 Products

GET /api/v1/products/ → Paginated product list

GET /api/v1/products/{id}/ → Product details

GET /api/v1/products/categories/ → Categories

Filtering: ?category=slug&min_price=100&max_price=500&in_stock=true

🛍️ Orders

GET /api/orders/cart/ → View cart

POST /api/orders/cart/add/ → Add to cart

POST /api/orders/create/ → Checkout order

GET /api/orders/ → Order history

⚙️ Admin

GET /api/admin/orders/ → All orders

PUT /api/admin/orders/{order_number}/status/ → Update order status

GET /api/v1/products/cache/stats/ → Cache info

⚙️ Production

Database: PostgreSQL config in settings.py

Cache: Redis with automatic invalidation

Env Vars:

SECRET_KEY=your-secret
DEBUG=False
DATABASE_URL=postgresql://user:pass@localhost:5432/ecommerce
REDIS_URL=redis://localhost:6379/1
ALLOWED_HOSTS=yourdomain.com

📊 Performance & Security

Redis caching: products (30m), categories (1h), search (5m)

DB optimization: indexes, related query loading

JWT expiry: Access (5 min), Refresh (7 days)

Role-based permissions & rate limiting

XSS, CSRF, and SQL injection protection


<div align="center">

🛒 Built with Django, DRF, Redis, Channels & Modern Web Technologies
<br/>Assignment Score: 100% Compliance ✅

</div>
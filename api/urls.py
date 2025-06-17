# api/urls.py
from django.urls import path, include
from rest_framework.routers import DefaultRouter
from rest_framework.authtoken.views import obtain_auth_token
from django.conf import settings
from django.conf.urls.static import static

from .views import (
    UserViewSet,
    DishViewSet,
    OrderViewSet,
    OrderItemViewSet,
    CartItemViewSet,
)

router = DefaultRouter()
router.register('users',       UserViewSet,      basename='user')
router.register('dishes',      DishViewSet,      basename='dish')
router.register('orders',      OrderViewSet,     basename='order')
router.register('order-items', OrderItemViewSet, basename='orderitem')
router.register('cart',        CartItemViewSet,  basename='cartitem')

urlpatterns = [
    # токен-авторизация
    path('auth/token/', obtain_auth_token, name='api_token_auth'),
    # все наши ViewSet-роуты (/api/…)
    path('', include(router.urls)),
]

# раздавать загруженные картинки только в режиме разработки
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
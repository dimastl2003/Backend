from django.urls import path, include
from rest_framework.routers import DefaultRouter
from rest_framework.authtoken.views import obtain_auth_token

from .views import (
    UserViewSet,
    DishViewSet,
    OrderViewSet,
    OrderItemViewSet,
    CartItemViewSet,
)

from django.conf import settings
from django.conf.urls.static import static

router = DefaultRouter()
# Регистрируем всех ViewSet
router.register(r'users', UserViewSet, basename='user')
router.register(r'dishes', DishViewSet, basename='dish')
router.register(r'orders', OrderViewSet, basename='order')
router.register(r'order-items', OrderItemViewSet, basename='orderitem')
router.register(r'cart', CartItemViewSet, basename='cartitem')

urlpatterns = [
    # токен-авторизация
    path('auth/token/', obtain_auth_token, name='api_token_auth'),
    # все остальные роуты
    path('', include(router.urls)),
]

# только в режиме разработки, чтобы Django сам раздавал файлы из MEDIA_ROOT
if settings.DEBUG:
    urlpatterns += static(
        settings.MEDIA_URL,
        document_root=settings.MEDIA_ROOT
    )
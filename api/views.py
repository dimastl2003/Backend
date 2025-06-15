from rest_framework import viewsets, permissions, status
from rest_framework.decorators import action
from rest_framework.response import Response
from django.contrib.auth import get_user_model
from django.db.models import Q
from .models import Dish, Order, CartItem, OrderItem
from .serializers import UserSerializer, DishSerializer, OrderSerializer, CartItemSerializer, OrderItemSerializer
from .permissions import IsAdmin, IsCook, IsCustomer
from rest_framework.parsers import MultiPartParser, FormParser

User = get_user_model()


class UserViewSet(viewsets.ModelViewSet):
    """
    - create (POST): регистрация — (AllowAny)
    - list / retrieve / update / delete: только админ (IsAdmin)
    - GET /api/users/me/   — текущему пользователю (IsAuthenticated)
    - GET /api/users/cooks/ — любой (AllowAny)
    """
    queryset = User.objects.all()
    serializer_class = UserSerializer

    def get_permissions(self):
        if self.action == 'create':
            return [permissions.AllowAny()]
        if self.action == 'me':
            return [permissions.IsAuthenticated()]
        if self.action == 'cooks':
            return [permissions.AllowAny()]
        if self.action == 'favorites':
            return [permissions.IsAuthenticated(), IsCustomer()]
        if self.action == 'add_favorite':
            return [permissions.IsAuthenticated(), IsCustomer()]
        if self.action == 'remove_favorite':
            return [permissions.IsAuthenticated(), IsCustomer()]
        # все остальные действия — только админ
        return [IsAdmin()]

    @action(detail=False, methods=['get'], permission_classes=[permissions.AllowAny])
    def cooks(self, request):
        cooks = User.objects.filter(role='cook')
        serializer = self.get_serializer(cooks, many=True)
        return Response(serializer.data)

    @action(detail=False, methods=['get', 'patch'], permission_classes=[permissions.IsAuthenticated])
    def me(self, request):
        user = request.user
        if request.method == 'GET':
            serializer = self.get_serializer(user)
            return Response(serializer.data)
        data = request.data.copy()
        password = data.pop('password', None)
        serializer = self.get_serializer(user, data=data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        if password:
            user.set_password(password)
            user.save()
        return Response(serializer.data, status=status.HTTP_200_OK)

    @action(detail=False, methods=['get'], permission_classes=[permissions.IsAuthenticated, IsCustomer])
    def favorites(self, request):
        """
        GET /api/users/favorites/
        Возвращает список избранных блюд текущего пользователя.
        """
        user = request.user
        favorite_dishes = user.favorite_dishes.all()
        serializer = DishSerializer(favorite_dishes, many=True)
        return Response(serializer.data)

    @action(detail=False, methods=['post'], permission_classes=[permissions.IsAuthenticated, IsCustomer])
    def add_favorite(self, request):
        """
        POST /api/users/add_favorite/
        JSON: {"dish_id": <int>}
        Добавляет указанное блюдо в избранное текущего пользователя.
        """
        user = request.user
        dish_id = request.data.get('dish_id')
        if dish_id is None:
            return Response({'detail': 'Не указан dish_id'}, status=status.HTTP_400_BAD_REQUEST)
        try:
            dish = Dish.objects.get(id=dish_id)
        except Dish.DoesNotExist:
            return Response({'detail': 'Блюдо не найдено'}, status=status.HTTP_404_NOT_FOUND)
        user.favorite_dishes.add(dish)
        return Response({'detail': f'Блюдо {dish.name} добавлено в избранное'}, status=status.HTTP_200_OK)

    @action(detail=False, methods=['delete'], permission_classes=[permissions.IsAuthenticated, IsCustomer])
    def remove_favorite(self, request):
        """
        DELETE /api/users/remove_favorite/
        JSON: {"dish_id": <int>}
        Убирает указанное блюдо из избранного текущего пользователя.
        """
        user = request.user
        dish_id = request.data.get('dish_id')
        if dish_id is None:
            return Response({'detail': 'Не указан dish_id'}, status=status.HTTP_400_BAD_REQUEST)
        try:
            dish = Dish.objects.get(id=dish_id)
        except Dish.DoesNotExist:
            return Response({'detail': 'Блюдо не найдено'}, status=status.HTTP_404_NOT_FOUND)
        user.favorite_dishes.remove(dish)
        return Response({'detail': f'Блюдо {dish.name} удалено из избранного'}, status=status.HTTP_200_OK)


class DishViewSet(viewsets.ModelViewSet):
    """
    CRUD для блюд:
      - create/update/delete: только повар (IsCook)
      - list/retrieve: любой аутентифицированный (IsAuthenticated)
    GET /api/dishes/?cook_id=<id> — фильтр по повару.
    """
    pagination_class = None
    serializer_class = DishSerializer
    parser_classes = (MultiPartParser, FormParser)

    def get_permissions(self):
        if self.action in ['create', 'update', 'partial_update', 'destroy']:
            return [IsCook()]
        return [permissions.IsAuthenticated()]

    def get_queryset(self):
        queryset = Dish.objects.all()
        cook_id = self.request.query_params.get('cook_id')

        if cook_id is not None:
            queryset = queryset.filter(cook__id=cook_id)

        # 2) фильтрация по поисковой строке: искать в name и description
        search_term = self.request.query_params.get('search')
        if search_term:
            queryset = queryset.filter(
                Q(name__icontains=search_term) |
                Q(description__icontains=search_term)
            )

        return queryset

    def perform_create(self, serializer):
        serializer.save(cook=self.request.user)


class OrderItemViewSet(viewsets.ModelViewSet):
    queryset = OrderItem.objects.all()
    serializer_class = OrderItemSerializer

    def get_permissions(self):
        # Изменять статус может только повар, у которого этот заказ
        if self.action in ['partial_update', 'update']:
            return [permissions.IsAuthenticated(), IsCook()]
        # Просмотр позиций внутри заказа оставить заказчику и админу
        return [permissions.IsAuthenticated()]

    def get_queryset(self):
        user = self.request.user
        if user.role == 'cook':
            # только свои позиции
            return OrderItem.objects.filter(order__cook=user)
        if user.role == 'customer':
            return OrderItem.objects.filter(order__customer=user)
        if user.role == 'admin':
            return OrderItem.objects.all()
        return OrderItem.objects.none()


class OrderViewSet(viewsets.ModelViewSet):
    """
    Order CRUD + action 'process':
      - create (POST) — только заказчик (IsCustomer)
      - list / retrieve —
          admin видит все,
          cook видит свои,
          customer видит свои
      - update/partial_update (PATCH) — только админ (IsAdmin)
      - destroy (DELETE) — только админ (IsAdmin)
      - POST /api/orders/{id}/process/ — только повар (IsCook), обрабатывает заказ
    """
    queryset = Order.objects.all()
    serializer_class = OrderSerializer

    def get_permissions(self):
        if self.action == 'create':
            return [permissions.IsAuthenticated(), IsCustomer()]
        if self.action in ['update', 'partial_update', 'destroy']:
            return [permissions.IsAuthenticated(), IsAdmin()]
        if self.action == 'process':
            return [permissions.IsAuthenticated(), IsCook()]
        # list / retrieve
        user = self.request.user
        if not user.is_authenticated:
            return [permissions.IsAuthenticated()]
        # админ может видеть всё
        if user.role == 'admin':
            return [permissions.IsAuthenticated()]
        # повар видит только свои, разрешение через вариант ниже
        if user.role == 'cook':
            return [permissions.IsAuthenticated(), IsCook()]
        # заказчик видит только свои
        if user.role == 'customer':
            return [permissions.IsAuthenticated(), IsCustomer()]
        return [permissions.IsAuthenticated()]

    def get_queryset(self):
        user = self.request.user
        if not user.is_authenticated:
            return Order.objects.none()

        if user.role == 'admin':
            return Order.objects.all()
        if user.role == 'cook':
            return Order.objects.filter(cook=user)
        if user.role == 'customer':
            return Order.objects.filter(customer=user)
        return Order.objects.none()

    def perform_create(self, serializer):
        # cook устанавливается через cook_id из сериализатора
        serializer.save(customer=self.request.user)

    @action(detail=True, methods=['post'], url_path='process')
    def process(self, request, pk=None):
        """
        Обработка заказа поваром.
        URL: POST /api/orders/{id}/process/
        Тело JSON:
        {
          "status": "accepted" | "rejected" | "in_progress" | "completed" | "cancelled",
          "rejection_reason": "текст при отклонении",
          "desired_ready_time": "2025-06-10T15:30:00Z"  # опционально
        }
        """
        order = self.get_object()

        # проверяем, что именно этот cook обрабатывает свой заказ
        if order.cook != request.user:
            return Response(
                {'detail': 'Нет прав обрабатывать этот заказ.'},
                status=status.HTTP_403_FORBIDDEN
            )

        status_param = request.data.get('status')
        reason = request.data.get('rejection_reason', '').strip()
        ready_time = request.data.get('desired_ready_time', None)

        if status_param not in ['accepted', 'rejected', 'in_progress', 'completed', 'cancelled']:
            return Response(
                {'detail': 'Неверный статус.'},
                status=status.HTTP_400_BAD_REQUEST
            )

        if status_param == 'rejected' and not reason:
            return Response(
                {'detail': 'Для отказа нужно указать причину.'},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Применяем изменения
        order.status = status_param
        if status_param == 'rejected':
            order.rejection_reason = reason
        else:
            # если статус не rejected, очищаем предыдущую причину (если была)
            order.rejection_reason = ''
        if ready_time is not None:
            order.desired_ready_time = ready_time

        order.save()
        serializer = self.get_serializer(order)
        return Response(serializer.data, status=status.HTTP_200_OK)

class CartItemViewSet(viewsets.ModelViewSet):
    """
    ViewSet для работы с элементами корзины:
      - list: GET /api/cart/          — список элементов корзины текущего пользователя
      - create: POST /api/cart/        — добавить блюдо (ид) + количество
      - retrieve: GET /api/cart/{id}/  — детальный элемент (необязательно)
      - update/partial_update: изменить количество
      - destroy: удалить элемент из корзины
    Доступ: только заказчик (IsCustomer).
    """
    serializer_class = CartItemSerializer

    def get_permissions(self):
        # Все операции — только для авторизованного пользователя с ролью 'customer'
        return [permissions.IsAuthenticated(), IsCustomer()]

    def get_queryset(self):
        # Возвращаем только те элементы корзины, которые принадлежат текущему user
        return CartItem.objects.filter(customer=self.request.user)

    def perform_create(self, serializer):
        # В create мы уже обрабатываем логику get_or_create в сериализаторе
        serializer.save(customer=self.request.user)

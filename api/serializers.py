from rest_framework import serializers
from django.contrib.auth import get_user_model
from .models import Dish, Order, OrderItem, CartItem

User = get_user_model()

class UserSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True)
    first_name = serializers.CharField(required=True, label='Имя')
    phone_number = serializers.CharField(required=False, label='Номер телефона')
    address = serializers.CharField(required=False, label='Адрес')

    favorite_dishes = serializers.PrimaryKeyRelatedField(
        many=True,
        read_only=True,
        help_text='Список ID избранных блюд'
    )

    class Meta:
        model = User
        fields = (
            'id',
            'username',
            'first_name',
            'email',
            'password',
            'role',
            'phone_number',
            'address',
            'favorite_dishes',
        )

    def validate(self, attrs):
        # Если роль 'cook', адрес обязателен
        role = attrs.get('role', self.instance.role if self.instance else None)
        address = attrs.get('address', '').strip()
        if role == 'cook' and not address:
            raise serializers.ValidationError({
                'address': 'Поле "Адрес" обязательно для роли Повар.'
            })
        return super().validate(attrs)

    def create(self, validated_data):
        username = validated_data['username']
        password = validated_data['password']
        role = validated_data.get('role', 'customer')
        email = validated_data.get('email', '')
        first_name = validated_data.get('first_name', '')
        phone = validated_data.get('phone_number', '')
        address = validated_data.get('address', '')

        user = User.objects.create_user(
            username=username,
            email=email,
            password=password,
            role=role,
        )
        user.first_name = first_name
        user.phone_number = phone
        user.address = address
        user.save()
        return user


class DishSerializer(serializers.ModelSerializer):
    cook = serializers.ReadOnlyField(source='cook.username')
    cook_address = serializers.ReadOnlyField(source='cook.address')
    image_url = serializers.SerializerMethodField()

    class Meta:
        model = Dish
        fields = (
            'id','name','description','price','cook','cook_address',
            'image','image_url','created_at'
        )
        read_only_fields = ('cook','created_at','image_url')

    def get_image_url(self, obj):
        request = self.context.get('request')
        if obj.image and hasattr(obj.image, 'url'):
            return request.build_absolute_uri(obj.image.url)
        return None


class OrderItemSerializer(serializers.ModelSerializer):
    dish = DishSerializer(read_only=True)
    dish_id = serializers.PrimaryKeyRelatedField(
        queryset=Dish.objects.all(),
        source='dish',
        write_only=True,
    )
    quantity = serializers.IntegerField(default=1)
    # Доступное поле статуса
    status = serializers.CharField(read_only=False)


    class Meta:
        model = OrderItem
        fields = ('id', 'dish', 'dish_id', 'quantity', 'status')


class OrderSerializer(serializers.ModelSerializer):
    customer = serializers.ReadOnlyField(source='customer.username')

    # Поле для записи: клиент отправляет cook_id
    cook_id = serializers.PrimaryKeyRelatedField(
        queryset=User.objects.filter(role='cook'),
        source='cook',
        write_only=True,
        help_text='Выберите ID повара',
    )
    cook = serializers.CharField(source='cook.username', read_only=True)

    # Список позиций, который выдается при GET (read_only=True)
    items = OrderItemSerializer(source='orderitem_set', many=True, read_only=True)

    # Поле dish_ids остается write_only, чтобы клиент мог передать список ID
    dish_ids = serializers.PrimaryKeyRelatedField(
        queryset=Dish.objects.all(),
        many=True,
        write_only=True,
        source='dishes',
    )

    rejection_reason = serializers.CharField(
        required=False, allow_blank=True, label='Причина отказа'
    )
    desired_ready_time = serializers.DateTimeField(
        required=False,
        allow_null=True,
        help_text='Время, к которому должно быть готово (ISO 8601)',
    )

    class Meta:
        model = Order
        fields = (
            'id',
            'customer',
            'cook_id',
            'cook',
            'status',
            'created_at',
            'updated_at',
            'items',
            'dish_ids',
            'rejection_reason',
            'desired_ready_time',
        )
        read_only_fields = ('status', 'created_at', 'updated_at')

    def validate(self, attrs):
        # Проверяем: все “dishes” (dish_ids) должны принадлежать указанному cook
        cook = attrs.get('cook')
        dishes = attrs.get('dishes', [])
        if cook and dishes:
            for dish in dishes:
                if dish.cook != cook:
                    raise serializers.ValidationError(
                        f"Блюдо «{dish.name}» не принадлежит повару «{cook.username}»."
                    )
        return super().validate(attrs)

    def create(self, validated_data):
        cook = validated_data.pop('cook')
        dishes = validated_data.pop('dishes', [])
        ready_time = validated_data.pop('desired_ready_time', None)
        request = self.context.get('request')
        customer = request.user

        order = Order.objects.create(
            customer=customer,
            cook=cook,
            status='pending',  # при создании всегда “pending”
            desired_ready_time=ready_time,
        )

        # Создаем OrderItem для каждого “dish”
        for dish in dishes:
            OrderItem.objects.create(order=order, dish=dish, quantity=1)

        return order

    def update(self, instance, validated_data):
        # Запретим клиенту менять статус напрямую через .PATCH /orders/{id}/
        # Здесь меняем только rejection_reason и desired_ready_time, если нужен
        instance.rejection_reason = validated_data.get('rejection_reason', instance.rejection_reason)
        instance.desired_ready_time = validated_data.get('desired_ready_time', instance.desired_ready_time)
        instance.save()
        return instance

class CartItemSerializer(serializers.ModelSerializer):
    dish = DishSerializer(read_only=True)
    dish_id = serializers.PrimaryKeyRelatedField(
        queryset=Dish.objects.all(),
        source='dish',
        write_only=True,
        help_text='ID блюда, которое добавляем в корзину'
    )
    quantity = serializers.IntegerField(default=1)

    class Meta:
        model = CartItem
        fields = ('id', 'dish', 'dish_id', 'quantity')
        read_only_fields = ('id', 'dish')

    def create(self, validated_data):
        # Если элемент корзины уже существует, увеличим количество
        request = self.context.get('request')
        customer = request.user
        dish = validated_data['dish']
        quantity = validated_data.get('quantity', 1)

        cart_item, created = CartItem.objects.get_or_create(
            customer=customer,
            dish=dish,
            defaults={'quantity': quantity}
        )
        if not created:
            cart_item.quantity += quantity
            cart_item.save()
        return cart_item

    def update(self, instance, validated_data):
        # Обновляем количество
        instance.quantity = validated_data.get('quantity', instance.quantity)
        instance.save()
        return instance

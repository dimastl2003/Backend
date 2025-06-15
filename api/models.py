from django.db import models

# Create your models here.

from django.contrib.auth.models import AbstractUser
from django.db import models

from django.conf import settings
from django.db import models

class User(AbstractUser):
    ROLE_CHOICES = (
        ('admin', 'Администратор'),
        ('cook', 'Повар'),
        ('customer', 'Заказчик'),
    )

    role = models.CharField(
        max_length=10,
        choices=ROLE_CHOICES,
        default='customer',
        verbose_name='Роль пользователя'
    )
    phone_number = models.CharField(
        max_length=20,
        blank=True,
        verbose_name='Номер телефона'
    )
    address = models.CharField(
        max_length=255,
        blank=True,
        verbose_name='Адрес'
    )
    favorite_dishes = models.ManyToManyField(
        'Dish',
        blank=True,
        related_name='favorited_by',
        verbose_name='Избранные блюда'
    )

    def __str__(self):
        return f"{self.username} ({self.get_role_display()})"


class Dish(models.Model):
    cook = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        limit_choices_to={'role': 'cook'},
        related_name='dishes',
        verbose_name='Повар'
    )
    name = models.CharField(max_length=255, verbose_name='Название')
    description = models.TextField(blank=True, verbose_name='Описание')
    price = models.DecimalField(max_digits=8, decimal_places=2, verbose_name='Цена')
    image = models.ImageField(
        upload_to='dishes/%Y/%m/%d/',
        null=True,
        blank=True,
        verbose_name='Фото блюда'
    )
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='Дата добавления')

    def __str__(self):
        return f"{self.name} — {self.cook.username}"


class Order(models.Model):
    STATUS_CHOICES = (
        ('pending', 'Новый'),
        ('accepted', 'Принят'),
        ('rejected', 'Отклонён'),
        ('in_progress', 'В процессе'),
        ('completed', 'Завершён'),
        ('cancelled', 'Отменён'),
    )

    customer = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        limit_choices_to={'role': 'customer'},
        related_name='orders',
        verbose_name='Заказчик'
    )
    cook = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        limit_choices_to={'role': 'cook'},
        related_name='orders_as_cook',
        verbose_name='Повар'
    )
    dishes = models.ManyToManyField(Dish, through='OrderItem', verbose_name='Блюда')
    status = models.CharField(
        max_length=15,
        choices=STATUS_CHOICES,
        default='pending',
        verbose_name='Статус'
    )
    rejection_reason = models.TextField(
        blank=True,
        verbose_name='Причина отказа',
        help_text='Заполняется только если статус = "rejected"'
    )
    desired_ready_time = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name='Время, к которому блюдо должно быть готово',
        help_text='Опционально: укажите дату и время готовности'
    )
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='Дата заказа')
    updated_at = models.DateTimeField(auto_now=True, verbose_name='Дата обновления')

    def __str__(self):
        return f"Заказ #{self.id} от {self.customer.username}"


class OrderItem(models.Model):
    order = models.ForeignKey(Order, on_delete=models.CASCADE, verbose_name='Заказ')
    dish = models.ForeignKey(Dish, on_delete=models.CASCADE, verbose_name='Блюдо')
    quantity = models.PositiveIntegerField(default=1, verbose_name='Количество')
    # Новый статус на уровне позиции заказа
    STATUS_CHOICES = (
        ('confirmed', 'Подтвержден'),
        ('in_progress', 'В процессе'),
        ('ready', 'Готово'),
    )
    status = models.CharField(
        max_length=12,
        choices=STATUS_CHOICES,
        default='confirmed',
        verbose_name='Статус блюда'
    )

    def __str__(self):
        return f"{self.dish.name} x {self.quantity}"

class CartItem(models.Model):
    """
    Корзинный элемент: каждый клиент (role='customer') может иметь несколько CartItem,
    каждый из которых хранит ссылку на Dish и количество.
    """
    customer = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        limit_choices_to={'role': 'customer'},
        related_name='cart_items',
        verbose_name='Заказчик'
    )
    dish = models.ForeignKey(
        Dish,
        on_delete=models.CASCADE,
        verbose_name='Блюдо'
    )
    quantity = models.PositiveIntegerField(default=1, verbose_name='Количество')

    class Meta:
        unique_together = ('customer', 'dish')
        verbose_name = 'Элемент корзины'
        verbose_name_plural = 'Элементы корзины'

    def __str__(self):
        return f"В корзине у {self.customer.username}: {self.dish.name} x {self.quantity}"
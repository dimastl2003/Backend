from django.contrib import admin

# Register your models here.

from django.contrib import admin
from .models import User, Dish, Order, OrderItem

@admin.register(User)
class UserAdmin(admin.ModelAdmin):
    list_display = ('username', 'email', 'role', 'is_staff', 'is_active')
    list_filter = ('role', 'is_staff', 'is_active')

@admin.register(Dish)
class DishAdmin(admin.ModelAdmin):
    list_display = ('name', 'cook', 'price', 'created_at')
    list_filter = ('cook',)
    search_fields = ('name',)

class OrderItemInline(admin.TabularInline):
    model = OrderItem
    extra = 0

@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    list_display = ('id', 'customer', 'cook', 'status', 'created_at')
    list_filter = ('status',)
    inlines = [OrderItemInline]
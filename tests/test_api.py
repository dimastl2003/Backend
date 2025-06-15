import tempfile
from datetime import datetime, timedelta

django_settings_module = 'settings'

from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase, APIClient
from django.contrib.auth import get_user_model
from api.models import Dish, Order, OrderItem, CartItem
from api.serializers import (
    UserSerializer, DishSerializer, OrderSerializer, OrderItemSerializer, CartItemSerializer
)

User = get_user_model()

class SerializerTests(APITestCase):
    def setUp(self):
        # create users
        self.admin = User.objects.create_user(username='admin', password='pass', role='admin')
        self.cook = User.objects.create_user(username='cook', password='pass', role='cook', address='Test Address')
        self.customer = User.objects.create_user(username='cust', password='pass', role='customer')
        # create dish by cook
        self.dish = Dish.objects.create(name='Soup', description='Tasty', price=5.0, cook=self.cook)
        # create order
        self.order = Order.objects.create(customer=self.customer, cook=self.cook, desired_ready_time=datetime.now()+timedelta(hours=1))
        self.item = OrderItem.objects.create(order=self.order, dish=self.dish, quantity=2)
        self.cart_item = CartItem.objects.create(customer=self.customer, dish=self.dish, quantity=1)

    def test_user_serializer_create(self):
        data = {
            'username': 'newuser',
            'password': 'newpass123',
            'first_name': 'John',
            'role': 'customer',
            'phone_number': '12345',
            'address': ''
        }
        serializer = UserSerializer(data=data)
        self.assertTrue(serializer.is_valid(), msg=serializer.errors)
        user = serializer.save()
        self.assertTrue(user.check_password('newpass123'))
        self.assertEqual(user.first_name, 'John')

    def test_dish_serializer_output(self):
        serializer = DishSerializer(self.dish, context={'request': None})
        data = serializer.data
        self.assertEqual(data['name'], 'Soup')
        self.assertEqual(data['cook'], self.cook.username)

    def test_order_serializer_create_and_validate(self):
        data = {
            'cook_id': self.cook.id,
            'dish_ids': [self.dish.id],
            'desired_ready_time': (datetime.now()+timedelta(hours=2)).isoformat()
        }
        context = {'request': type('req', (), {'user': self.customer})()}
        serializer = OrderSerializer(data=data, context=context)
        self.assertTrue(serializer.is_valid(), msg=serializer.errors)
        order = serializer.save()
        self.assertEqual(order.status, 'pending')
        self.assertEqual(order.orderitem_set.count(), 1)

    def test_orderitem_serializer(self):
        serializer = OrderItemSerializer(self.item)
        data = serializer.data
        self.assertEqual(data['quantity'], 2)
        self.assertIn('dish', data)
        self.assertIn('status', data)

    def test_cartitem_serializer_create(self):
        data = {'dish_id': self.dish.id, 'quantity': 3}
        context = {'request': type('req', (), {'user': self.customer})()}
        serializer = CartItemSerializer(data=data, context=context)
        self.assertTrue(serializer.is_valid(), msg=serializer.errors)
        cart_item = serializer.save()
        self.assertEqual(cart_item.quantity, 3)

class ViewSetTests(APITestCase):
    def setUp(self):
        self.client = APIClient()
        # create users
        self.cust = User.objects.create_user(username='cust', password='pass', role='customer')
        self.cook = User.objects.create_user(username='cook', password='pass', role='cook', address='Addr')
        self.admin = User.objects.create_user(username='adm', password='pass', role='admin')
        # login admin
        self.client.login(username='adm', password='pass')

    def test_list_cooks_endpoint(self):
        url = reverse('user-cooks')
        resp = self.client.get(url)
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertTrue(isinstance(resp.data, list))

    def test_dish_crud_by_cook(self):
        # cook login
        self.client.login(username='cook', password='pass')
        # create dish
        url = reverse('dish-list')
        resp = self.client.post(url, {'name':'Pasta','description':'Yum','price':'10.5'})
        self.assertEqual(resp.status_code, status.HTTP_201_CREATED)
        dish_id = resp.data['id']
        # update dish
        url_detail = reverse('dish-detail', args=[dish_id])
        resp2 = self.client.patch(url_detail, {'price':'12.0'})
        self.assertEqual(resp2.status_code, status.HTTP_200_OK)

    def test_order_process_by_cook(self):
        # create order as customer
        self.client.login(username='cust', password='pass')
        dish = Dish.objects.create(name='Fish', price=8.0, cook=self.cook)
        url = reverse('order-list')
        resp = self.client.post(url, {'cook_id': self.cook.id, 'dish_ids':[dish.id]})
        self.assertEqual(resp.status_code, status.HTTP_201_CREATED)
        order_id = resp.data['id']
        # cook process
        self.client.login(username='cook', password='pass')
        url_proc = reverse('order-process', args=[order_id])
        resp3 = self.client.post(url_proc, {'status':'accepted'})
        self.assertEqual(resp3.status_code, status.HTTP_200_OK)

class BusinessLogicTests(APITestCase):
    def test_default_orderitem_status(self):
        cook = User.objects.create_user(username='cook2', password='pass', role='cook', address='addr')
        cust = User.objects.create_user(username='cust2', password='pass', role='customer')
        dish = Dish.objects.create(name='Stew', price=7.0, cook=cook)
        order = Order.objects.create(customer=cust, cook=cook)
        item = OrderItem.objects.create(order=order, dish=dish, quantity=1)
        self.assertEqual(item.status, 'confirmed')

    def test_orderitem_status_transition(self):
        # ensure status can change and saved
        cook = User.objects.create_user(username='cook3', password='pass', role='cook', address='addr')
        cust = User.objects.create_user(username='cust3', password='pass', role='customer')
        dish = Dish.objects.create(name='Cake', price=4.0, cook=cook)
        order = Order.objects.create(customer=cust, cook=cook)
        item = OrderItem.objects.create(order=order, dish=dish, quantity=1)
        item.status = 'in_progress'
        item.save()
        refreshed = OrderItem.objects.get(id=item.id)
        self.assertEqual(refreshed.status, 'in_progress')
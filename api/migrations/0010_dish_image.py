# Generated by Django 5.2.1 on 2025-06-16 00:42

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('api', '0009_orderitem_status'),
    ]

    operations = [
        migrations.AddField(
            model_name='dish',
            name='image',
            field=models.ImageField(blank=True, null=True, upload_to='dishes/%Y/%m/%d/', verbose_name='Фото блюда'),
        ),
    ]

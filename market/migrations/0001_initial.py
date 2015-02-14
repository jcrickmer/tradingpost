# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations
import django.utils.timezone


class Migration(migrations.Migration):

    dependencies = [
    ]

    operations = [
        migrations.CreateModel(
            name='BuyOrder',
            fields=[
                ('id', models.AutoField(serialize=False, primary_key=True)),
                ('quantity', models.IntegerField()),
                ('order_type', models.CharField(default=b'market', max_length=12, choices=[(b'limit', b'limit'), (b'market', b'market')])),
                ('price', models.FloatField(null=True)),
                ('placed_datetime', models.DateTimeField(default=django.utils.timezone.now, auto_now=True)),
                ('fill_by_datetime', models.DateTimeField(null=True)),
            ],
            options={
            },
            bases=(models.Model,),
        ),
        migrations.CreateModel(
            name='Inventory',
            fields=[
                ('id', models.AutoField(serialize=False, primary_key=True)),
                ('quantity', models.IntegerField(default=0)),
                ('added_datetime', models.DateTimeField(default=django.utils.timezone.now, auto_now=True)),
                ('value', models.FloatField()),
            ],
            options={
            },
            bases=(models.Model,),
        ),
        migrations.CreateModel(
            name='Participant',
            fields=[
                ('id', models.AutoField(serialize=False, primary_key=True)),
            ],
            options={
            },
            bases=(models.Model,),
        ),
        migrations.CreateModel(
            name='SellOrder',
            fields=[
                ('id', models.AutoField(serialize=False, primary_key=True)),
                ('quantity', models.IntegerField()),
                ('order_type', models.CharField(default=b'market', max_length=12, choices=[(b'limit', b'limit'), (b'market', b'market')])),
                ('price', models.FloatField(null=True)),
                ('placed_datetime', models.DateTimeField(default=django.utils.timezone.now, auto_now=True)),
                ('fill_by_datetime', models.DateTimeField(null=True)),
                ('inventory', models.ForeignKey(to='market.Inventory')),
                ('seller', models.ForeignKey(to='market.Participant')),
            ],
            options={
            },
            bases=(models.Model,),
        ),
        migrations.CreateModel(
            name='Stock',
            fields=[
                ('id', models.AutoField(serialize=False, primary_key=True)),
            ],
            options={
            },
            bases=(models.Model,),
        ),
        migrations.CreateModel(
            name='Transaction',
            fields=[
                ('id', models.AutoField(serialize=False, primary_key=True)),
                ('price', models.FloatField()),
                ('filled_datetime', models.DateTimeField(default=django.utils.timezone.now, auto_now=True)),
                ('buy_order', models.ForeignKey(to='market.BuyOrder')),
                ('sell_order', models.ForeignKey(to='market.SellOrder')),
            ],
            options={
            },
            bases=(models.Model,),
        ),
        migrations.AddField(
            model_name='inventory',
            name='owner',
            field=models.ForeignKey(to='market.Participant'),
            preserve_default=True,
        ),
        migrations.AddField(
            model_name='inventory',
            name='related_buy',
            field=models.ForeignKey(to='market.BuyOrder', null=True),
            preserve_default=True,
        ),
        migrations.AddField(
            model_name='inventory',
            name='stock',
            field=models.ForeignKey(to='market.Stock'),
            preserve_default=True,
        ),
        migrations.AddField(
            model_name='buyorder',
            name='buyer',
            field=models.ForeignKey(to='market.Participant'),
            preserve_default=True,
        ),
        migrations.AddField(
            model_name='buyorder',
            name='stock',
            field=models.ForeignKey(to='market.Stock'),
            preserve_default=True,
        ),
    ]

# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations
import django.utils.timezone


class Migration(migrations.Migration):

    dependencies = [
        ('market', '0001_initial'),
    ]

    operations = [
        migrations.CreateModel(
            name='Account',
            fields=[
                ('id', models.AutoField(serialize=False, primary_key=True)),
                ('funds', models.FloatField()),
                ('owner', models.ForeignKey(to='market.Participant', unique=True)),
            ],
            options={
            },
            bases=(models.Model,),
        ),
        migrations.CreateModel(
            name='ExternalMarketPrice',
            fields=[
                ('id', models.AutoField(serialize=False, primary_key=True)),
                ('price_datetime', models.DateTimeField(default=django.utils.timezone.now, auto_now=True)),
                ('price', models.FloatField()),
                ('stock', models.ForeignKey(to='market.Stock')),
            ],
            options={
            },
            bases=(models.Model,),
        ),
    ]

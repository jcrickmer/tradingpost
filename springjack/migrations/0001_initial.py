# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations
import django.utils.timezone

def init_escrow_account(apps, schema_editor):
    Participant = apps.get_model("market", "Participant")
    hoodwink = Participant()
    hoodwink.name = 'HoodwinkEscrowOfficer'
    hoodwink.save()

class Migration(migrations.Migration):

    dependencies = [
        ('market', '__first__'),
    ]

    operations = [
        migrations.CreateModel(
            name='Account',
            fields=[
                ('id', models.AutoField(serialize=False, primary_key=True)),
                ('owner', models.ForeignKey(to='market.Participant')),
            ],
            options={
            },
            bases=(models.Model,),
        ),
        migrations.CreateModel(
            name='LedgerEntry',
            fields=[
                ('id', models.AutoField(serialize=False, primary_key=True)),
                ('entry_datetime', models.DateTimeField(default=django.utils.timezone.now, auto_now=True)),
                ('amount', models.FloatField()),
                ('other_memo', models.CharField(max_length=100)),
                ('txid', models.CharField(max_length=100)),
                ('account', models.ForeignKey(related_name='account', to='springjack.Account')),
                ('other_account', models.ForeignKey(related_name='other_account', to='springjack.Account', null=True)),
            ],
            options={
            },
            bases=(models.Model,),
        ),
        migrations.RunPython(init_escrow_account),
    ]

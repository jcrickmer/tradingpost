from django.db import models
from datetime import datetime
from django.utils import timezone

from django.db.models import Q, Count, Min, Sum, Avg

import sys


class Participant(models.Model):
    id = models.AutoField(primary_key=True)

    def __unicode__(self):
        return '[Participant ' + str(self.id) + ']'


class BuyOrder(models.Model):
    id = models.AutoField(primary_key=True)
    buyer = models.ForeignKey('Participant', null=False)
    quantity = models.IntegerField(null=False)
    stock = models.ForeignKey('Stock', null=False)
    LIMIT_ORDER = 'limit'
    #STOP_ORDER = 'stop'
    MARKET_ORDER = 'market'
    ORDER_CHOICES = ((LIMIT_ORDER, LIMIT_ORDER),
                     #(STOP_ORDER, STOP_ORDER),
                     (MARKET_ORDER, MARKET_ORDER))
    order_type = models.CharField(max_length=12, choices=ORDER_CHOICES, default=MARKET_ORDER)
    price = models.FloatField(null=True)
    placed_datetime = models.DateTimeField(default=timezone.now, auto_now=True, null=False)
    fill_by_datetime = models.DateTimeField(null=True)

    STATUS_OPEN = 'open'
    STATUS_FILLED = 'filled'
    STATUS_EXPIRED = 'expired'

    def status(self):
        ''' Check to see if the order is still valid. '''
        if self.fill_by_datetime is not None and self.fill_by_datetime < timezone.now():
            return self.STATUS_EXPIRED

        if self.get_transaction is not None:
            return self.STATUS_FILLED

        return STATUS.OPEN

    def get_transaction(self):
        for xaction in Transaction.objects.filter(buy_order=self).all():
            return xaction


class SellOrder(models.Model):
    id = models.AutoField(primary_key=True)
    seller = models.ForeignKey('Participant')
    quantity = models.IntegerField(null=False)
    inventory = models.ForeignKey('Inventory', null=False)
    LIMIT_ORDER = 'limit'
    #STOP_ORDER = 'stop'
    MARKET_ORDER = 'market'
    ORDER_CHOICES = ((LIMIT_ORDER, LIMIT_ORDER),
                     #(STOP_ORDER, STOP_ORDER),
                     (MARKET_ORDER, MARKET_ORDER))
    order_type = models.CharField(max_length=12, choices=ORDER_CHOICES, default=MARKET_ORDER)
    price = models.FloatField(null=True)
    placed_datetime = models.DateTimeField(default=timezone.now, auto_now=True, null=False)
    fill_by_datetime = models.DateTimeField(null=True)

    def __unicode__(self):
        return '[SellOrder ' + str(self.id) + ': ' + str(self.seller) + ' selling ' + str(self.quantity) + \
            ' ' + str(self.inventory.stock) + ' at ' + str(self.price) + ' as ' + str(self.order_type) + ']'


class Transaction(models.Model):
    id = models.AutoField(primary_key=True)
    buy_order = models.ForeignKey('BuyOrder', null=False)
    sell_order = models.ForeignKey('SellOrder', null=False)
    price = models.FloatField(null=False)
    filled_datetime = models.DateTimeField(default=timezone.now, auto_now=True, null=False)
    # For now, quantity must match


class Stock(models.Model):
    id = models.AutoField(primary_key=True)

    def __unicode__(self):
        return '[Stock ' + str(self.id) + ']'


class InventoryManager(models.Manager):

    def count(self, owner, stock):
        ''' Look at all of the inventory for this owner for the given stock, and add it all up. Should always return 0 or a positive integer. '''
        result = 0
        qr = Inventory.objects.filter(owner=owner, stock=stock).aggregate(Sum('quantity'))
        if qr is not None and qr['quantity__sum'] is not None:
            result = qr['quantity__sum']
        return result


class Inventory(models.Model):
    id = models.AutoField(primary_key=True)
    owner = models.ForeignKey('Participant', null=False)
    stock = models.ForeignKey('Stock', null=False)
    quantity = models.IntegerField(default=0, null=False)
    added_datetime = models.DateTimeField(default=timezone.now, auto_now=True, null=False)
    value = models.FloatField(null=False)
    related_buy = models.ForeignKey('BuyOrder', null=True)

    objects = models.Manager()
    manager = InventoryManager()

    def __unicode__(self):
        return '[Inventory {}: ]'.format(self.id)


class Market():

    def match(self):
        # do the logic to match buyers and sellers, and create transactions as needed
        pass

    def current_bid_price(self, stock):
        buyorder = BuyOrder.objects.filter(stock=stock).exclude(order_type=BuyOrder.MARKET_ORDER).order_by('-price').first()
        if buyorder is not None:
            return buyorder.price
        else:
            return None

    def current_ask_price(self, stock):
        sellorder = SellOrder.objects.filter(inventory__stock=stock).exclude(order_type=SellOrder.MARKET_ORDER).order_by('price').first()
        if sellorder is not None:
            return sellorder.price
        else:
            return None

    def current_market_price(self, stock):
        result = None

        # First, let's just get the most recent transaction and use it to determine market price
        transaction = Transaction.objects.filter(stock=stock).order_by('-filled_datetime')
        if transaction is not None:
            result = transaction.price

        if result is None:
            # REVISIT - well, let's pick a different strategy
            pass

        return result

    def clear_market(self):
        ''' Match buyers and selers. '''

        # Find all open buys.
        buys = BuyOrder.objects.filter(Q(fill_by_datetime__lte=timezone.now()) | Q(fill_by_datetime=None), transaction=None)

        # Fore each of these buys, let's see if we can find someone willing to sell at that price
        for buyorder in buys:
            sys.stderr.write(str(buyorder.buyer) + " is looking for seller of " + str(buyorder.stock))
            # You cannot buy from yourself.
            sellorder_qs = SellOrder.objects.exclude(seller=buyorder.buyer)
            # Only look at stock that we are buying
            sellorder_qs = sellorder_qs.filter(inventory__stock=buyorder.stock)
            # for sell orders that have not yet expired
            sellorder_qs = sellorder_qs.filter(Q(fill_by_datetime__lte=timezone.now()) | Q(fill_by_datetime=None))
            # the have not already been transacted
            sellorder_qs = sellorder_qs.filter(transaction=None)
            if buyorder.order_type == buyorder.MARKET_ORDER:
                sys.stderr.write(" at market price.\n")
                # Market order...
                pass
            else:
                sys.stderr.write(" at no more than " + str(buyorder.price) + "\n")
                # Limit order... constrain by price.
                sellorder_qs = sellorder_qs.filter(price__lte=buyorder.price)

            # and of course look for the best price
            sellorder_qs = sellorder_qs.order_by('price')

            sellorder = sellorder_qs.first()

            if sellorder is not None:
                # let's make a deal!!
                # REVISIT - we should make this all atomic!!!

                sys.stderr.write("Woot! look at " + str(sellorder) + "\n")
                # first, create a transaction
                xaction = Transaction()
                xaction.buy_order = buyorder
                xaction.sell_order = sellorder
                if buyorder.order_type == buyorder.MARKET_ORDER:
                    xaction.price = sellorder.price  # REVISIT - this may not be the price because the sell order could be market, not limit
                else:
                    xaction.price = buyorder.price
                xaction.save()
                # now move the inventory
                seller_out_inv = Inventory()
                seller_out_inv.owner = sellorder.seller
                seller_out_inv.stock = sellorder.inventory.stock
                seller_out_inv.quantity = -1
                seller_out_inv.value = xaction.price
                seller_out_inv.save()
                buyer_in_inv = Inventory()
                buyer_in_inv.owner = buyorder.buyer
                buyer_in_inv.stock = sellorder.inventory.stock
                buyer_in_inv.quantity = 1
                buyer_in_inv.value = xaction.price
                buyer_in_inv.related_buy = buyorder
                buyer_in_inv.save()

                # now move the money
                # REVISIT - haven't even looked at money yet!
        # Find all open sells.

        # Match them.

        pass

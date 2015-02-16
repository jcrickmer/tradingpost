from django.db import models
from datetime import datetime
from django.utils import timezone

from django.db.models import Q, Count, Min, Sum, Avg

import sys


class Stock(models.Model):
    id = models.AutoField(primary_key=True)

    def __unicode__(self):
        return '[Stock {}]'.format(str(self.id))


class Participant(models.Model):
    id = models.AutoField(primary_key=True)
    name = models.CharField(max_length=100, null=False, unique=True)

    def __unicode__(self):
        return '[Participant {} {}]'.format(str(self.id), self.name)


class BuyOrder(models.Model):
    id = models.AutoField(primary_key=True)
    buyer = models.ForeignKey('Participant', null=False)
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

    def __unicode__(self):
        return '[BuyOrder {}: {} selling {} at {} as {}]'.format(
            str(
                self.id), str(
                self.buyer), str(
                self.stock), str(
                    self.price), str(
                        self.order_type))


class SellOrder(models.Model):
    id = models.AutoField(primary_key=True)
    seller = models.ForeignKey('Participant')
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
        for xaction in Transaction.objects.filter(sell_order=self).all():
            return xaction

    def __unicode__(self):
        return '[SellOrder {}: {} selling {} at {} as {}]'.format(
            str(
                self.id), str(
                self.seller), str(
                self.inventory.stock), str(
                    self.price), str(
                        self.order_type))


class Transaction(models.Model):
    id = models.AutoField(primary_key=True)
    buy_order = models.ForeignKey('BuyOrder', null=False)
    sell_order = models.ForeignKey('SellOrder', null=False)
    price = models.FloatField(null=False)
    initiated_datetime = models.DateTimeField(default=timezone.now, auto_now=False, null=False)
    shipped_datetime = models.DateTimeField(auto_now=False, null=True)
    completed_datetime = models.DateTimeField(auto_now=False, null=True)
    # For now, quantity must match

    OPEN_STATUS = 'open'
    SHIPPED_STATUS = 'shipped'
    CLOSED_STATUS = 'closed'
    STATUS_CHOICES = ((OPEN_STATUS, OPEN_STATUS),
                      (SHIPPED_STATUS, SHIPPED_STATUS),
                      (CLOSED_STATUS, CLOSED_STATUS))
    status = models.CharField(max_length=12, choices=STATUS_CHOICES, default=OPEN_STATUS)

    def ship(self):
        self.status = self.SHIPPED_STATUS
        self.shipped_datetime = timezone.now()
        self.save()
        self.sell_order.inventory.status = Inventory.SHIPPED_STATUS
        self.sell_order.inventory.save()

    def close(self):
        self.status = self.CLOSED_STATUS
        self.completed_datetime = timezone.now()
        self.save()

        self.sell_order.inventory.deliver_to(self.buy_order, self.price)
        self.sell_order.inventory.save()

    def __unicode__(self):
        return '[Transaction {}: {} sold {} to {} for {} at {}]'.format(
            self.id,
            self.sell_order.seller,
            self.buy_order.stock,
            self.buy_order.buyer,
            self.price,
            self.filled_datetime)


class InventoryManager(models.Manager):

    '''
    Look at all of the inventory for this owner for the given stock,
    and add it all up. Should always return 0 or a positive integer.
    '''

    def count(self, owner, stock):
        result = 0
        qr = Inventory.objects.filter(owner=owner, stock=stock, status=Inventory.AVAILABLE_STATUS).aggregate(Count('id'))
        if qr is not None and qr['id__count'] is not None:
            result = qr['id__count']
        return result


class Inventory(models.Model):
    id = models.AutoField(primary_key=True)
    owner = models.ForeignKey('Participant', null=False)
    stock = models.ForeignKey('Stock', null=False)
    added_datetime = models.DateTimeField(default=timezone.now, auto_now=True, null=False)
    value = models.FloatField(null=False)
    related_buy = models.ForeignKey('BuyOrder', null=True)

    AVAILABLE_STATUS = 'available'
    SOLD_STATUS = 'sold'
    SHIPPED_STATUS = 'shipped'
    DELIVERED_STATUS = 'delivered'
    STATUS_CHOICES = ((AVAILABLE_STATUS, AVAILABLE_STATUS),
                      (SOLD_STATUS, SOLD_STATUS),
                      (SHIPPED_STATUS, SHIPPED_STATUS),
                      (DELIVERED_STATUS, DELIVERED_STATUS))
    status = models.CharField(max_length=12, choices=STATUS_CHOICES, default=AVAILABLE_STATUS)

    objects = models.Manager()
    manager = InventoryManager()

    def deliver_to(self, buy_order, price):
        self.status = Inventory.DELIVERED_STATUS
        newinv = Inventory()
        newinv.owner = buy_order.buyer
        newinv.stock = self.stock
        newinv.value = price
        newinv.related_buy = buy_order
        newinv.save()

    def __unicode__(self):
        return '[Inventory {}: ]'.format(self.id)


class ExternalMarketPrice(models.Model):
    id = models.AutoField(primary_key=True)
    stock = models.ForeignKey('Stock', null=False)
    price_datetime = models.DateTimeField(default=timezone.now, auto_now=True, null=False)
    price = models.FloatField(null=False)


class Market():

    def __init__(self, rishada):
        self.rishada = rishada

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
        transaction = Transaction.objects.filter(buy_order__stock=stock).order_by('-initiated_datetime').first()
        if transaction is not None:
            result = transaction.price

        if result is None:
            # Well, let's look for an external market price
            emp = ExternalMarketPrice.objects.filter(stock=stock).order_by('-price_datetime').first()
            if emp is not None:
                result = emp.price
            else:
                # raise an error?
                pass

        return result

    '''
    Match buyers and selers.
    '''

    def clear_market(self):

        # Find all open buys.
        buys = BuyOrder.objects.filter(Q(fill_by_datetime__lte=timezone.now()) | Q(fill_by_datetime=None), transaction=None)

        # Fore each of these buys, let's see if we can find someone willing to sell at that price
        for buyorder in buys:
            #sys.stderr.write(str(buyorder.buyer) + " is looking for seller of " + str(buyorder.stock))
            # You cannot buy from yourself.
            sellorder_qs = SellOrder.objects.exclude(seller=buyorder.buyer)
            # Only look at stock that we are buying
            sellorder_qs = sellorder_qs.filter(inventory__stock=buyorder.stock)
            # for sell orders that have not yet expired
            sellorder_qs = sellorder_qs.filter(Q(fill_by_datetime__lte=timezone.now()) | Q(fill_by_datetime=None))
            # the have not already been transacted
            sellorder_qs = sellorder_qs.filter(transaction=None)
            if buyorder.order_type == buyorder.MARKET_ORDER:
                #sys.stderr.write(" at market price.\n")
                # Market order...
                pass
            else:
                #sys.stderr.write(" at no more than " + str(buyorder.price) + "\n")
                # Limit order... constrain by price.
                sellorder_qs = sellorder_qs.filter(
                    Q(order_type=SellOrder.LIMIT_ORDER, price__lte=buyorder.price) | Q(order_type=SellOrder.MARKET_ORDER))

            # and of course look for the best price
            sellorder_qs = sellorder_qs.order_by('price')
            # REVISIT - Need to make sure that we transact the oldest orders at the lowest price first.

            sellorder = sellorder_qs.first()
            #sys.stderr.write("sellorder is " + str(sellorder) + "\n")
            if sellorder is not None:
                # let's make a deal!!
                # REVISIT - we should make this all atomic!!!

                #sys.stderr.write("Woot! look at " + str(sellorder) + "\n")
                # first, figure out the price.
                xaction_price = sellorder.price
                if xaction_price is None:
                    xaction_price = buyorder.price

                if buyorder.order_type == buyorder.MARKET_ORDER and sellorder.order_type == sellorder.MARKET_ORDER and xaction_price is None:
                    xaction_price = self.current_market_price(buyorder.stock)

                # second, does the buyer have money?
                buy_address = buyorder.buyer.account_set.first().get_account_id()
                if self.rishada.get_balance(buy_address) < xaction_price:
                    # no dice
                    continue

                escrow_owner = Participant.objects.filter(name='HoodwinkEscrowOfficer').first()
                if escrow_owner is None:
                    raise Error('Make this a real error.')

                # REVISIT - need to wrap all of this in a transaction.

                # third, create a transaction
                xaction = Transaction()
                xaction.buy_order = buyorder
                xaction.sell_order = sellorder
                xaction.price = xaction_price
                xaction.save()

                # now move the inventory
                seller_out_inv = sellorder.inventory
                seller_out_inv.status = Inventory.SOLD_STATUS
                seller_out_inv.save()

                # last move the money
                sell_address = sellorder.seller.account_set.first().get_account_id()
                self.rishada.escrow_funds(buy_address, xaction.id, xaction.price)

                #buy_acct = Account.objects.filter(owner=buyorder.buyer).first()
                #sell_acct = Account.objects.filter(owner=sellorder.seller).first()
                #buy_acct.funds = buy_acct.funds - xaction.price
                #sell_acct.funds = sell_acct.funds + xaction.price
                # buy_acct.save()
                # sell_acct.save()
                ##sys.stderr.write(str(xaction) + "\n")
        pass

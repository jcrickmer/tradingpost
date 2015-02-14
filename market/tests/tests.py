# -*- coding: utf-8 -*-
from django.test import TestCase
from django_nose import FastFixtureTestCase
from django.db import IntegrityError
from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone

from market.models import Participant, BuyOrder, SellOrder, Transaction, Stock, Inventory, Market

import sys
err = sys.stderr

# Create your tests here.


class BasicTestCase(TestCase):

    def test_create_participant(self):
        part = Participant()
        self.assertIsNotNone(part)
        part.save()
        self.assertIsNotNone(part)
        self.assertIsNotNone(part.id)

    def test_create_2_participants(self):
        part1 = Participant()
        part1.save()
        part2 = Participant()
        part2.save()

        part1 = Participant.objects.get(pk=part1.id)
        part2 = Participant.objects.get(pk=part2.id)

        self.assertNotEqual(part1, part2)
        self.assertNotEqual(part1.id, part2.id)

    def test_create_stock(self):
        stock = Stock()
        self.assertIsNotNone(stock)
        stock.save()
        self.assertIsNotNone(stock)
        self.assertIsNotNone(stock.id)

    def test_create_2_stocks(self):
        stock1 = Stock()
        stock1.save()
        stock2 = Stock()
        stock2.save()

        stock1 = Stock.objects.get(pk=stock1.id)
        stock2 = Stock.objects.get(pk=stock2.id)

        self.assertNotEqual(stock1, stock2)
        self.assertNotEqual(stock1.id, stock2.id)

    def test_create_inventory(self):
        part = Participant()
        part.save()
        stock = Stock()
        stock.save()

        inv = Inventory()
        inv.owner = part
        inv.quantity = 1
        inv.stock = stock
        inv.value = .5
        inv.save()

        inv = Inventory.objects.get(pk=inv.id)
        self.assertIsNotNone(inv)
        self.assertIsNotNone(inv.id)
        self.assertEqual(inv.owner.id, part.id)
        self.assertEqual(inv.stock.id, stock.id)
        self.assertEqual(inv.value, .5)
        self.assertEqual(inv.quantity, 1)

    def test_create_buyorder(self):
        part = Participant()
        part.save()
        stock = Stock()
        stock.save()

        buy = BuyOrder()
        buy.buyer = part
        buy.stock = stock
        buy.quantity = 1
        buy.order_type = BuyOrder.MARKET_ORDER
        buy.save()

        buy = BuyOrder.objects.get(pk=buy.id)
        self.assertIsNotNone(buy)
        self.assertEquals(buy.stock.id, stock.id)
        self.assertEquals(buy.buyer.id, part.id)
        self.assertEquals(buy.quantity, 1)
        self.assertEquals(buy.order_type, BuyOrder.MARKET_ORDER)
        self.assertLessEqual(buy.placed_datetime, timezone.now())
        self.assertIsNone(buy.fill_by_datetime)

    def test_create_sellorder(self):
        part = Participant()
        part.save()
        stock = Stock()
        stock.save()

        inv = Inventory()
        inv.owner = part
        inv.stock = stock
        inv.quantity = 1
        inv.value = .5
        inv.save()

        sell = SellOrder()
        sell.seller = part
        sell.inventory = inv
        sell.quantity = 1
        sell.order_type = SellOrder.MARKET_ORDER
        sell.save()

        sell = SellOrder.objects.get(pk=sell.id)
        self.assertIsNotNone(sell)
        self.assertEquals(sell.inventory.id, inv.id)
        self.assertEquals(sell.seller.id, part.id)
        self.assertEquals(sell.quantity, 1)
        self.assertEquals(sell.order_type, SellOrder.MARKET_ORDER)
        self.assertLessEqual(sell.placed_datetime, timezone.now())
        self.assertIsNone(sell.fill_by_datetime)

    def test_market_bid_ask_price(self):
        ''' The current bid price should be the max of all of the non-transacted bids for a stock. '''
        ''' The current ask price should be the min of all of the non-transacted asks for a stock. '''

        stock = Stock()
        stock.save()

        seller = Participant()
        seller.save()

        inv = Inventory()
        inv.owner = seller
        inv.stock = stock
        inv.quantity = 1
        inv.value = .5
        inv.save()

        sell = SellOrder()
        sell.seller = seller
        sell.inventory = inv
        sell.quantity = 1
        sell.order_type = SellOrder.LIMIT_ORDER
        sell.price = .55
        sell.save()
        sell = SellOrder.objects.get(pk=sell.id)

        buyer = Participant()
        buyer.save()

        buy = BuyOrder()
        buy.buyer = buyer
        buy.stock = stock
        buy.quantity = 1
        buy.order_type = BuyOrder.LIMIT_ORDER
        buy.price = .45
        buy.save()
        buy = BuyOrder.objects.get(pk=buy.id)

        market = Market()
        self.assertEquals(.55, market.current_ask_price(stock))
        self.assertEquals(.45, market.current_bid_price(stock))

    def test_market_simple_transaction(self):
        stock = Stock()
        stock.save()

        seller = Participant()
        seller.save()

        inv = Inventory()
        inv.owner = seller
        inv.stock = stock
        inv.quantity = 1
        inv.value = .5
        inv.save()

        sell = SellOrder()
        sell.seller = seller
        sell.inventory = inv
        sell.quantity = 1
        sell.order_type = SellOrder.LIMIT_ORDER
        sell.price = .51
        sell.save()
        sell = SellOrder.objects.get(pk=sell.id)

        buyer = Participant()
        buyer.save()

        buy = BuyOrder()
        buy.buyer = buyer
        buy.stock = stock
        buy.quantity = 1
        buy.order_type = BuyOrder.LIMIT_ORDER
        buy.price = .51
        buy.save()
        buy = BuyOrder.objects.get(pk=buy.id)

        market = Market()
        self.assertEquals(.51, market.current_ask_price(stock))
        self.assertEquals(.51, market.current_bid_price(stock))

        # seller should have 1 item of this stock in inventory.
        self.assertEquals(Inventory.manager.count(seller, stock), 1)
        # buyer should have none.
        self.assertEquals(Inventory.manager.count(buyer, stock), 0)

        market.clear_market()

        xactions = Transaction.objects.filter(buy_order=buy)
        self.assertEquals(xactions.count(), 1)
        xaction = xactions[0]
        self.assertEquals(xaction, buy.get_transaction())
        self.assertEquals(xaction.buy_order.id, buy.id)
        self.assertEquals(xaction.sell_order.id, sell.id)
        self.assertEquals(xaction.price, .51)

        self.assertLessEqual(xaction.filled_datetime, timezone.now())

        # seller should have reduced inventory.
        self.assertEquals(Inventory.manager.count(seller, stock), 0)
        # buyer should have inventory.
        self.assertEquals(Inventory.manager.count(buyer, stock), 1)

    ''' You cannot assign inventory to an owner unless the related_buy is None, or the BuyOrder.owner is the same as the Inventory.owner.'''

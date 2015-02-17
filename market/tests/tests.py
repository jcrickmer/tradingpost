# -*- coding: utf-8 -*-
from django.test import TestCase
from django_nose import FastFixtureTestCase
from django.db import IntegrityError
from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone

from market.models import Participant, BuyOrder, SellOrder, Transaction, Stock, Inventory, Market, ExternalMarketPrice

from rishada.rishada import Rishada, InsufficientFundsError

from springjack.models import Springjack, Account, LedgerEntry

from django.db.models import Q, Count, Min, Sum, Avg
import uuid
import sys
err = sys.stderr


class BasicTestCase(TestCase):

    def test_create_participant(self):
        part = Participant()
        self.assertIsNotNone(part)
        part.name = 'Nancy'
        part.save()
        self.assertIsNotNone(part)
        self.assertIsNotNone(part.id)

    def test_create_2_participants(self):
        part1 = Participant()
        part1.name = 'Wilbur'
        part1.save()
        part2 = Participant()
        part2.name = 'Juan'
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
        part.name = 'Greg'
        part.save()
        stock = Stock()
        stock.save()

        inv = Inventory()
        inv.owner = part
        inv.stock = stock
        inv.value = .5
        inv.save()

        inv = Inventory.objects.get(pk=inv.id)
        self.assertIsNotNone(inv)
        self.assertIsNotNone(inv.id)
        self.assertEqual(inv.owner.id, part.id)
        self.assertEqual(inv.stock.id, stock.id)
        self.assertEqual(inv.value, .5)
        self.assertEqual(inv.status, Inventory.AVAILABLE_STATUS)

    def test_create_buyorder(self):
        part = Participant()
        part.name = 'Alice'
        part.save()
        stock = Stock()
        stock.save()

        buy = BuyOrder()
        buy.buyer = part
        buy.stock = stock
        buy.order_type = BuyOrder.MARKET_ORDER
        buy.save()

        buy = BuyOrder.objects.get(pk=buy.id)
        self.assertIsNotNone(buy)
        self.assertEquals(buy.stock.id, stock.id)
        self.assertEquals(buy.buyer.id, part.id)
        self.assertEquals(buy.order_type, BuyOrder.MARKET_ORDER)
        self.assertLessEqual(buy.placed_datetime, timezone.now())
        self.assertIsNone(buy.fill_by_datetime)

    def test_create_sellorder(self):
        part = Participant()
        part.name = 'Beth'
        part.save()
        stock = Stock()
        stock.save()

        inv = Inventory()
        inv.owner = part
        inv.stock = stock
        inv.value = .5
        inv.save()

        sell = SellOrder()
        sell.seller = part
        sell.inventory = inv
        sell.order_type = SellOrder.MARKET_ORDER
        sell.save()

        sell = SellOrder.objects.get(pk=sell.id)
        self.assertIsNotNone(sell)
        self.assertEquals(sell.inventory.id, inv.id)
        self.assertEquals(sell.seller.id, part.id)
        self.assertEquals(sell.order_type, SellOrder.MARKET_ORDER)
        self.assertLessEqual(sell.placed_datetime, timezone.now())
        self.assertIsNone(sell.fill_by_datetime)

    def test_market_bid_ask_price(self):
        ''' The current bid price should be the max of all of the non-transacted bids for a stock. '''
        ''' The current ask price should be the min of all of the non-transacted asks for a stock. '''

        stock = Stock()
        stock.save()

        seller = Participant()
        seller.name = 'Samantha'
        seller.save()

        inv = Inventory()
        inv.owner = seller
        inv.stock = stock
        inv.value = .5
        inv.save()

        sell = SellOrder()
        sell.seller = seller
        sell.inventory = inv
        sell.order_type = SellOrder.LIMIT_ORDER
        sell.price = .55
        sell.save()
        sell = SellOrder.objects.get(pk=sell.id)

        buyer = Participant()
        buyer.name = 'Beck'
        buyer.save()

        buy = BuyOrder()
        buy.buyer = buyer
        buy.stock = stock
        buy.order_type = BuyOrder.LIMIT_ORDER
        buy.price = .45
        buy.save()
        buy = BuyOrder.objects.get(pk=buy.id)

        springjack = Springjack()
        rishada = Rishada(springjack)
        market = Market(rishada)
        self.assertEquals(.55, market.current_ask_price(stock))
        self.assertEquals(.45, market.current_bid_price(stock))

    """ One Buyer, one Seller, one stock
    Buyer has sufficient funds
    BuyOrder is LIMIT
    SellOrder is LIMIT
    Orders match, transaction results
    order ships and buyer confirms
    """

    def test_clear_market_simple_transaction(self):
        seller_init_funds = 1.75
        buyer_init_funds = 3.0
        buy_price = .51
        sell_price = buy_price
        escrow_owner = Participant.objects.filter(name='HoodwinkEscrowOfficer').first()

        base_economy = seller_init_funds + buyer_init_funds

        springjack = Springjack()
        rishada = Rishada(springjack)
        market = Market(rishada)

        stock = Stock()
        stock.save()

        # SELLER
        seller = Participant()
        seller.name = 'Seller Joe'
        seller.save()

        # Setup the seller account with some money
        saccount = rishada.create_account(seller.id)

        sile = LedgerEntry()
        sile.account = saccount
        sile.amount = seller_init_funds
        sile.other_memo = 'starting balance'
        sile.txid = 'fakedit0'
        sile.save()

        self.assertEquals(rishada.get_balance(saccount.get_account_id()), seller_init_funds)

        inv = Inventory()
        inv.owner = seller
        inv.stock = stock
        inv.value = .5
        inv.save()

        sell = SellOrder()
        sell.seller = seller
        sell.inventory = inv
        sell.order_type = SellOrder.LIMIT_ORDER
        sell.price = sell_price
        # this essentially places the order in the market
        sell.save()
        sell = SellOrder.objects.get(pk=sell.id)

        # BUYER
        buyer = Participant()
        buyer.name = 'Buyer Bob'
        buyer.save()

        # Setup the buyer account with some money
        baccount = rishada.create_account(buyer.id)

        bile = LedgerEntry()
        bile.account = baccount
        bile.amount = buyer_init_funds
        bile.other_memo = 'buyer starting balance'
        bile.txid = 'fakedit1'
        bile.save()

        self.assertEquals(rishada.get_balance(baccount.get_account_id()), buyer_init_funds)

        buy = BuyOrder()
        buy.buyer = buyer
        buy.stock = stock
        buy.order_type = BuyOrder.LIMIT_ORDER
        buy.price = buy_price
        # this essentially places the order in the market
        buy.save()
        buy = BuyOrder.objects.get(pk=buy.id)

        # Test market
        self.assertEquals(buy_price, market.current_ask_price(stock))
        self.assertEquals(buy_price, market.current_bid_price(stock))

        # seller should have 1 item of this stock in inventory.
        self.assertEquals(Inventory.manager.count(seller, stock), 1)
        # buyer should have none.
        self.assertEquals(Inventory.manager.count(buyer, stock), 0)

        # Connect buyers and sellers
        market.clear_market()

        # Check to make sure no money has entered or left the system
        cur_economy = LedgerEntry.objects.all().aggregate(Sum('amount'))['amount__sum']
        self.assertEquals(cur_economy, base_economy)

        # TEST that clear_market() made the right transaction
        xaction_count = Transaction.objects.all().count()
        xactions = Transaction.objects.filter(buy_order=buy)
        self.assertEquals(xactions.count(), 1)
        xaction = xactions[0]
        self.assertEquals(xaction, buy.get_transaction())
        self.assertEquals(xaction.buy_order.id, buy.id)
        self.assertEquals(xaction.sell_order.id, sell.id)
        self.assertEquals(xaction.price, buy_price)

        self.assertLessEqual(xaction.initiated_datetime, timezone.now())
        self.assertIsNone(xaction.shipped_datetime)
        self.assertIsNone(xaction.completed_datetime)

        # seller should have reduced inventory.
        self.assertEquals(Inventory.manager.count(seller, stock), 0)

        # buyer doesn't have it yet...
        self.assertEquals(Inventory.manager.count(buyer, stock), 0)

        # seller inventory should be statused as sold
        inv = Inventory.objects.get(pk=inv.id)
        self.assertEquals(inv.status, Inventory.SOLD_STATUS)

        # seller does not have funds yet - they are in escrow
        self.assertEquals(rishada.get_balance(saccount.get_account_id()), seller_init_funds)

        # but buyer is out the money
        self.assertEquals(rishada.get_balance(baccount.get_account_id()), buyer_init_funds - buy_price)

        # Check to make sure no money has entered or left the system
        cur_economy = LedgerEntry.objects.all().aggregate(Sum('amount'))['amount__sum']
        self.assertEquals(cur_economy, base_economy)

        # and market price should be updated.
        self.assertEquals(market.current_market_price(stock), buy_price)

        # one last check to make sure that clearing the market again doesn't dup any transactions
        market.clear_market()
        self.assertEquals(Transaction.objects.all().count(), xaction_count)
        self.assertEquals(market.current_market_price(stock), buy_price)

        # seller ships it
        xaction.ship()

        # buyer gets it!
        xaction.close()

        # yay, the buyer got their goods!
        rishada.release_escrow(rishada.get_account_by_participant_id(xaction.sell_order.seller.id).get_account_id(), xaction.id)

        # seller inventory should be statused as delivered
        inv = Inventory.objects.get(pk=inv.id)
        self.assertEquals(inv.status, Inventory.DELIVERED_STATUS)

        # buyer is still out the money
        self.assertEquals(rishada.get_balance(baccount.get_account_id()), buyer_init_funds - buy_price)

        # seller has his money!
        self.assertEquals(rishada.get_balance(saccount.get_account_id()), seller_init_funds + buy_price)

        # and market price should still be buy_price
        self.assertEquals(market.current_market_price(stock), buy_price)

        # buyer should have some inventory...
        binv = Inventory.objects.filter(owner=buyer).first()
        self.assertEquals(binv.value, buy_price)

        # Check to make sure no money has entered or left the system
        cur_economy = LedgerEntry.objects.all().aggregate(Sum('amount'))['amount__sum']
        self.assertEquals(cur_economy, base_economy)

    """ One Buyer, one Seller, one stock
    Buyer has sufficient funds
    BuyOrder is MARKET
    SellOrder is MARKET
    no MARKET history, so external price is used
    Orders match, transaction results
    order ships and buyer confirms
    """

    def test_clear_market_b_mark_funded_s_mark(self):
        seller_init_funds = 1.75
        # FUNDED
        buyer_init_funds = 3.0
        market_price = .4875

        escrow_owner = Participant.objects.filter(name='HoodwinkEscrowOfficer').first()

        base_economy = seller_init_funds + buyer_init_funds

        springjack = Springjack()
        rishada = Rishada(springjack)
        market = Market(rishada)

        stock = Stock()
        stock.save()

        # Establish external market price
        emp = ExternalMarketPrice()
        emp.price = market_price
        emp.stock = stock
        emp.save()

        # SELLER
        seller = Participant()
        seller.name = 'Margo'
        seller.save()

        # Setup the seller account with some money
        saccount = rishada.create_account(seller.id)

        sile = LedgerEntry()
        sile.account = saccount
        sile.amount = seller_init_funds
        sile.other_memo = 'starting balance'
        sile.txid = 'fakedit0'
        sile.save()

        self.assertEquals(rishada.get_balance(saccount.get_account_id()), seller_init_funds)

        inv = Inventory()
        inv.owner = seller
        inv.stock = stock
        inv.value = .5
        inv.save()

        sell = SellOrder()
        sell.seller = seller
        sell.inventory = inv
        sell.order_type = SellOrder.MARKET_ORDER
        # this essentially places the order in the market
        sell.save()
        sell = SellOrder.objects.get(pk=sell.id)

        # BUYER
        buyer = Participant()
        buyer.name = 'Wilhem'
        buyer.save()

        # Setup the buyer account with some money
        baccount = rishada.create_account(buyer.id)

        bile = LedgerEntry()
        bile.account = baccount
        bile.amount = buyer_init_funds
        bile.other_memo = 'buyer starting balance'
        bile.txid = 'fakedit1'
        bile.save()

        self.assertEquals(rishada.get_balance(baccount.get_account_id()), buyer_init_funds)

        buy = BuyOrder()
        buy.buyer = buyer
        buy.stock = stock
        buy.order_type = BuyOrder.MARKET_ORDER
        # this essentially places the order in the market
        buy.save()
        buy = BuyOrder.objects.get(pk=buy.id)

        # Test market
        self.assertEquals(market_price, market.current_market_price(stock))

        # seller should have 1 item of this stock in inventory.
        self.assertEquals(Inventory.manager.count(seller, stock), 1)
        # buyer should have none.
        self.assertEquals(Inventory.manager.count(buyer, stock), 0)

        # seller should have 1 item of this stock in inventory.
        self.assertEquals(Inventory.manager.count(seller, stock), 1)
        # buyer should have none.
        self.assertEquals(Inventory.manager.count(buyer, stock), 0)

        # Connect buyers and sellers
        market.clear_market()

        # Check to make sure no money has entered or left the system
        cur_economy = LedgerEntry.objects.all().aggregate(Sum('amount'))['amount__sum']
        self.assertEquals(cur_economy, base_economy)

        # TEST that clear_market() made the right transaction
        xaction_count = Transaction.objects.all().count()
        xactions = Transaction.objects.filter(buy_order=buy)
        self.assertEquals(xactions.count(), 1)
        xaction = xactions[0]
        self.assertEquals(xaction, buy.get_transaction())
        self.assertEquals(xaction.buy_order.id, buy.id)
        self.assertEquals(xaction.sell_order.id, sell.id)
        self.assertEquals(xaction.price, market_price)

        self.assertLessEqual(xaction.initiated_datetime, timezone.now())
        self.assertIsNone(xaction.shipped_datetime)
        self.assertIsNone(xaction.completed_datetime)

        # seller should have reduced inventory.
        self.assertEquals(Inventory.manager.count(seller, stock), 0)

        # buyer doesn't have it yet...
        self.assertEquals(Inventory.manager.count(buyer, stock), 0)

        # seller inventory should be statused as sold
        inv = Inventory.objects.get(pk=inv.id)
        self.assertEquals(inv.status, Inventory.SOLD_STATUS)

        # seller does not have funds yet - they are in escrow
        self.assertEquals(rishada.get_balance(saccount.get_account_id()), seller_init_funds)

        # but buyer is out the money
        self.assertEquals(rishada.get_balance(baccount.get_account_id()), buyer_init_funds - market_price)

        # and market price should be updated.
        self.assertEquals(market.current_market_price(stock), market_price)

        # one last check to make sure that clearing the market again doesn't dup any transactions
        market.clear_market()
        self.assertEquals(Transaction.objects.all().count(), xaction_count)
        self.assertEquals(market.current_market_price(stock), market_price)

        # seller ships it
        xaction.ship()

        # buyer gets it!
        xaction.close()

        # yay, the buyer got their goods!
        rishada.release_escrow(rishada.get_account_by_participant_id(xaction.sell_order.seller.id).get_account_id(), xaction.id)

        # seller inventory should be statused as delivered
        inv = Inventory.objects.get(pk=inv.id)
        self.assertEquals(inv.status, Inventory.DELIVERED_STATUS)

        # buyer is still out the money
        self.assertEquals(rishada.get_balance(baccount.get_account_id()), buyer_init_funds - market_price)

        # seller has his money!
        self.assertEquals(rishada.get_balance(saccount.get_account_id()), seller_init_funds + market_price)

        # and market price should still be market_price
        self.assertEquals(market.current_market_price(stock), market_price)

        # buyer should have some inventory...
        binv = Inventory.objects.filter(owner=buyer).first()
        self.assertEquals(binv.value, market_price)

        # Check to make sure no money has entered or left the system
        cur_economy = LedgerEntry.objects.all().aggregate(Sum('amount'))['amount__sum']
        self.assertEquals(cur_economy, base_economy)

    """ One Buyer, one Seller, one stock
    Buyer lacks sufficient funds
    BuyOrder is MARKET
    SellOrder is MARKET
    no MARKET history, so external price is used
    Orders do not match, no transaction
    """

    def test_clear_market_b_mark_unfunded_s_mark(self):
        seller_init_funds = 1.75
        # UNFUNDED
        buyer_init_funds = 0.44444
        market_price = .4875

        escrow_owner = Participant.objects.filter(name='HoodwinkEscrowOfficer').first()

        base_economy = seller_init_funds + buyer_init_funds

        springjack = Springjack()
        rishada = Rishada(springjack)
        market = Market(rishada)

        stock = Stock()
        stock.save()

        # Establish external market price
        emp = ExternalMarketPrice()
        emp.price = market_price
        emp.stock = stock
        emp.save()

        # SELLER
        seller = Participant()
        seller.name = 'Margo'
        seller.save()

        # Setup the seller account with some money
        saccount = rishada.create_account(seller.id)

        sile = LedgerEntry()
        sile.account = saccount
        sile.amount = seller_init_funds
        sile.other_memo = 'starting balance'
        sile.txid = 'fakedit0'
        sile.save()

        self.assertEquals(rishada.get_balance(saccount.get_account_id()), seller_init_funds)

        inv = Inventory()
        inv.owner = seller
        inv.stock = stock
        inv.value = .5
        inv.save()

        sell = SellOrder()
        sell.seller = seller
        sell.inventory = inv
        sell.order_type = SellOrder.MARKET_ORDER
        # this essentially places the order in the market
        sell.save()
        sell = SellOrder.objects.get(pk=sell.id)

        # BUYER
        buyer = Participant()
        buyer.name = 'Wilhem'
        buyer.save()

        # Setup the buyer account with some money
        baccount = rishada.create_account(buyer.id)

        bile = LedgerEntry()
        bile.account = baccount
        bile.amount = buyer_init_funds
        bile.other_memo = 'buyer starting balance'
        bile.txid = 'fakedit1'
        bile.save()

        self.assertEquals(rishada.get_balance(baccount.get_account_id()), buyer_init_funds)

        buy = BuyOrder()
        buy.buyer = buyer
        buy.stock = stock
        buy.order_type = BuyOrder.MARKET_ORDER
        # this essentially places the order in the market
        buy.save()
        buy = BuyOrder.objects.get(pk=buy.id)

        # Test market
        self.assertEquals(market_price, market.current_market_price(stock))

        # seller should have 1 item of this stock in inventory.
        self.assertEquals(Inventory.manager.count(seller, stock), 1)
        # buyer should have none.
        self.assertEquals(Inventory.manager.count(buyer, stock), 0)

        # seller should have 1 item of this stock in inventory.
        self.assertEquals(Inventory.manager.count(seller, stock), 1)
        # buyer should have none.
        self.assertEquals(Inventory.manager.count(buyer, stock), 0)

        # Connect buyers and sellers
        market.clear_market()

        # Check to make sure no money has entered or left the system
        cur_economy = LedgerEntry.objects.all().aggregate(Sum('amount'))['amount__sum']
        self.assertEquals(cur_economy, base_economy)

        # TEST that clear_market() made the right transaction
        xaction_count = Transaction.objects.all().count()
        xactions = Transaction.objects.filter(buy_order=buy)
        self.assertEquals(xactions.count(), 0)

        # seller should have same inventory.
        self.assertEquals(Inventory.manager.count(seller, stock), 1)

        # buyer doesn't get anything
        self.assertEquals(Inventory.manager.count(buyer, stock), 0)

        # seller inventory should be still show available
        inv = Inventory.objects.get(pk=inv.id)
        self.assertEquals(inv.status, Inventory.AVAILABLE_STATUS)

        # seller hasn't lost any money
        self.assertEquals(rishada.get_balance(saccount.get_account_id()), seller_init_funds)

        # buyer still has all of his money
        self.assertEquals(rishada.get_balance(baccount.get_account_id()), buyer_init_funds)

        # and market price has not changed
        self.assertEquals(market.current_market_price(stock), market_price)

        # one last check to make sure that clearing the market again doesn't dup any transactions
        market.clear_market()
        self.assertEquals(Transaction.objects.all().count(), xaction_count)
        self.assertEquals(market.current_market_price(stock), market_price)

        # Check to make sure no money has entered or left the system
        cur_economy = LedgerEntry.objects.all().aggregate(Sum('amount'))['amount__sum']
        self.assertEquals(cur_economy, base_economy)

    """ One Buyer, one Seller, one stock
    Buyer has sufficient funds
    BuyOrder is LIMIT
    SellOrder is MARKET
    Orders match, transaction results
    order ships and buyer confirms
    an external market price exists
    """

    def test_clear_market_b_lim_funded_s_mark_match_with_ext_market_price(self):
        seller_init_funds = 1.75
        # FUNDED
        buyer_init_funds = 3.0
        buy_price = .4875
        ext_market_price = 0.89

        escrow_owner = Participant.objects.filter(name='HoodwinkEscrowOfficer').first()

        base_economy = seller_init_funds + buyer_init_funds

        springjack = Springjack()
        rishada = Rishada(springjack)
        market = Market(rishada)

        stock = Stock()
        stock.save()

        # Establish external market price
        emp = ExternalMarketPrice()
        emp.price = ext_market_price
        emp.stock = stock
        emp.save()

        # SELLER
        seller = Participant()
        seller.name = 'Margo'
        seller.save()

        # Setup the seller account with some money
        saccount = rishada.create_account(seller.id)

        sile = LedgerEntry()
        sile.account = saccount
        sile.amount = seller_init_funds
        sile.other_memo = 'starting balance'
        sile.txid = 'fakedit0'
        sile.save()

        self.assertEquals(rishada.get_balance(saccount.get_account_id()), seller_init_funds)

        inv = Inventory()
        inv.owner = seller
        inv.stock = stock
        inv.value = .5
        inv.save()

        sell = SellOrder()
        sell.seller = seller
        sell.inventory = inv
        sell.order_type = SellOrder.MARKET_ORDER
        # this essentially places the order in the market
        sell.save()
        sell = SellOrder.objects.get(pk=sell.id)

        # BUYER
        buyer = Participant()
        buyer.name = 'Wilhem'
        buyer.save()

        # Setup the buyer account with some money
        baccount = rishada.create_account(buyer.id)

        bile = LedgerEntry()
        bile.account = baccount
        bile.amount = buyer_init_funds
        bile.other_memo = 'buyer starting balance'
        bile.txid = 'fakedit1'
        bile.save()

        self.assertEquals(rishada.get_balance(baccount.get_account_id()), buyer_init_funds)

        buy = BuyOrder()
        buy.buyer = buyer
        buy.stock = stock
        buy.order_type = BuyOrder.LIMIT_ORDER
        buy.price = buy_price
        # this essentially places the order in the market
        buy.save()
        buy = BuyOrder.objects.get(pk=buy.id)

        # Test market
        self.assertEquals(market.current_market_price(stock), ext_market_price)

        # seller should have 1 item of this stock in inventory.
        self.assertEquals(Inventory.manager.count(seller, stock), 1)
        # buyer should have none.
        self.assertEquals(Inventory.manager.count(buyer, stock), 0)

        # Connect buyers and sellers
        market.clear_market()

        # Check to make sure no money has entered or left the system
        cur_economy = LedgerEntry.objects.all().aggregate(Sum('amount'))['amount__sum']
        self.assertEquals(cur_economy, base_economy)

        # TEST that clear_market() made the right transaction
        xaction_count = Transaction.objects.all().count()
        xactions = Transaction.objects.filter(buy_order=buy)
        self.assertEquals(xactions.count(), 1)
        xaction = xactions[0]
        self.assertEquals(xaction, buy.get_transaction())
        self.assertEquals(xaction.buy_order.id, buy.id)
        self.assertEquals(xaction.sell_order.id, sell.id)
        self.assertEquals(xaction.price, buy_price)
        self.assertNotEquals(xaction.price, ext_market_price)

        self.assertLessEqual(xaction.initiated_datetime, timezone.now())
        self.assertIsNone(xaction.shipped_datetime)
        self.assertIsNone(xaction.completed_datetime)

        # seller should have reduced inventory.
        self.assertEquals(Inventory.manager.count(seller, stock), 0)

        # buyer doesn't have it yet...
        self.assertEquals(Inventory.manager.count(buyer, stock), 0)

        # seller inventory should be statused as sold
        inv = Inventory.objects.get(pk=inv.id)
        self.assertEquals(inv.status, Inventory.SOLD_STATUS)

        # seller does not have funds yet - they are in escrow
        self.assertEquals(rishada.get_balance(saccount.get_account_id()), seller_init_funds)

        # but buyer is out the money
        self.assertEquals(rishada.get_balance(baccount.get_account_id()), buyer_init_funds - buy_price)

        # and market price should be updated.
        self.assertEquals(market.current_market_price(stock), buy_price)

        # one last check to make sure that clearing the market again doesn't dup any transactions
        market.clear_market()
        self.assertEquals(Transaction.objects.all().count(), xaction_count)
        self.assertEquals(market.current_market_price(stock), buy_price)

        # seller ships it
        xaction.ship()

        # buyer gets it!
        xaction.close()

        # yay, the buyer got their goods!
        rishada.release_escrow(rishada.get_account_by_participant_id(xaction.sell_order.seller.id).get_account_id(), xaction.id)

        # seller inventory should be statused as delivered
        inv = Inventory.objects.get(pk=inv.id)
        self.assertEquals(inv.status, Inventory.DELIVERED_STATUS)

        # buyer is still out the money
        self.assertEquals(rishada.get_balance(baccount.get_account_id()), buyer_init_funds - buy_price)

        # seller has his money!
        self.assertEquals(rishada.get_balance(saccount.get_account_id()), seller_init_funds + buy_price)

        # and market price should now be the buy_price
        self.assertEquals(market.current_market_price(stock), buy_price)

        # buyer should have some inventory...
        binv = Inventory.objects.filter(owner=buyer).first()
        self.assertEquals(binv.value, buy_price)

        # Check to make sure no money has entered or left the system
        cur_economy = LedgerEntry.objects.all().aggregate(Sum('amount'))['amount__sum']
        self.assertEquals(cur_economy, base_economy)

    """ One Buyer, one Seller, one stock
    Buyer has sufficient funds
    BuyOrder is LIMIT
    SellOrder is MARKET
    Orders match, transaction results
    order ships and buyer confirms
    NO external market price exists
    """

    def test_clear_market_b_lim_funded_s_mark_match_no_ext_market_price(self):
        seller_init_funds = 1.75
        # FUNDED
        buyer_init_funds = 3.0
        buy_price = .4875

        escrow_owner = Participant.objects.filter(name='HoodwinkEscrowOfficer').first()

        base_economy = seller_init_funds + buyer_init_funds

        springjack = Springjack()
        rishada = Rishada(springjack)
        market = Market(rishada)

        stock = Stock()
        stock.save()

        # SELLER
        seller = Participant()
        seller.name = 'Margo'
        seller.save()

        # Setup the seller account with some money
        saccount = rishada.create_account(seller.id)

        sile = LedgerEntry()
        sile.account = saccount
        sile.amount = seller_init_funds
        sile.other_memo = 'starting balance'
        sile.txid = 'fakedit0'
        sile.save()

        self.assertEquals(rishada.get_balance(saccount.get_account_id()), seller_init_funds)

        inv = Inventory()
        inv.owner = seller
        inv.stock = stock
        inv.value = .5
        inv.save()

        sell = SellOrder()
        sell.seller = seller
        sell.inventory = inv
        sell.order_type = SellOrder.MARKET_ORDER
        # this essentially places the order in the market
        sell.save()
        sell = SellOrder.objects.get(pk=sell.id)

        # BUYER
        buyer = Participant()
        buyer.name = 'Wilhem'
        buyer.save()

        # Setup the buyer account with some money
        baccount = rishada.create_account(buyer.id)

        bile = LedgerEntry()
        bile.account = baccount
        bile.amount = buyer_init_funds
        bile.other_memo = 'buyer starting balance'
        bile.txid = 'fakedit1'
        bile.save()

        self.assertEquals(rishada.get_balance(baccount.get_account_id()), buyer_init_funds)

        buy = BuyOrder()
        buy.buyer = buyer
        buy.stock = stock
        buy.order_type = BuyOrder.LIMIT_ORDER
        buy.price = buy_price
        # this essentially places the order in the market
        buy.save()
        buy = BuyOrder.objects.get(pk=buy.id)

        # Test market
        self.assertIsNone(market.current_market_price(stock))

        # seller should have 1 item of this stock in inventory.
        self.assertEquals(Inventory.manager.count(seller, stock), 1)
        # buyer should have none.
        self.assertEquals(Inventory.manager.count(buyer, stock), 0)

        # Connect buyers and sellers
        market.clear_market()

        # Check to make sure no money has entered or left the system
        cur_economy = LedgerEntry.objects.all().aggregate(Sum('amount'))['amount__sum']
        self.assertEquals(cur_economy, base_economy)

        # TEST that clear_market() made the right transaction
        xaction_count = Transaction.objects.all().count()
        xactions = Transaction.objects.filter(buy_order=buy)
        self.assertEquals(xactions.count(), 1)
        xaction = xactions[0]
        self.assertEquals(xaction, buy.get_transaction())
        self.assertEquals(xaction.buy_order.id, buy.id)
        self.assertEquals(xaction.sell_order.id, sell.id)
        self.assertEquals(xaction.price, buy_price)

        self.assertLessEqual(xaction.initiated_datetime, timezone.now())
        self.assertIsNone(xaction.shipped_datetime)
        self.assertIsNone(xaction.completed_datetime)

        # seller should have reduced inventory.
        self.assertEquals(Inventory.manager.count(seller, stock), 0)

        # buyer doesn't have it yet...
        self.assertEquals(Inventory.manager.count(buyer, stock), 0)

        # seller inventory should be statused as sold
        inv = Inventory.objects.get(pk=inv.id)
        self.assertEquals(inv.status, Inventory.SOLD_STATUS)

        # seller does not have funds yet - they are in escrow
        self.assertEquals(rishada.get_balance(saccount.get_account_id()), seller_init_funds)

        # but buyer is out the money
        self.assertEquals(rishada.get_balance(baccount.get_account_id()), buyer_init_funds - buy_price)

        # and market price should be updated.
        self.assertEquals(market.current_market_price(stock), buy_price)

        # one last check to make sure that clearing the market again doesn't dup any transactions
        market.clear_market()
        self.assertEquals(Transaction.objects.all().count(), xaction_count)
        self.assertEquals(market.current_market_price(stock), buy_price)

        # seller ships it
        xaction.ship()

        # buyer gets it!
        xaction.close()

        # yay, the buyer got their goods!
        rishada.release_escrow(rishada.get_account_by_participant_id(xaction.sell_order.seller.id).get_account_id(), xaction.id)

        # seller inventory should be statused as delivered
        inv = Inventory.objects.get(pk=inv.id)
        self.assertEquals(inv.status, Inventory.DELIVERED_STATUS)

        # buyer is still out the money
        self.assertEquals(rishada.get_balance(baccount.get_account_id()), buyer_init_funds - buy_price)

        # seller has his money!
        self.assertEquals(rishada.get_balance(saccount.get_account_id()), seller_init_funds + buy_price)

        # and market price should now be the buy_price
        self.assertEquals(market.current_market_price(stock), buy_price)

        # buyer should have some inventory...
        binv = Inventory.objects.filter(owner=buyer).first()
        self.assertEquals(binv.value, buy_price)

        # Check to make sure no money has entered or left the system
        cur_economy = LedgerEntry.objects.all().aggregate(Sum('amount'))['amount__sum']
        self.assertEquals(cur_economy, base_economy)

    """ One Buyer, one Seller, one stock
    Buyer does not have sufficient funds
    BuyOrder is LIMIT
    SellOrder is MARKET
    Orders match but insufficient funds, no transaction
    external market price exists
    """

    def test_clear_market_b_lim_unfunded_s_mark_match(self):
        seller_init_funds = 1.75
        # FUNDED
        buyer_init_funds = 0.313131
        buy_price = .4875
        ext_market_price = 0.89

        escrow_owner = Participant.objects.filter(name='HoodwinkEscrowOfficer').first()

        base_economy = seller_init_funds + buyer_init_funds

        springjack = Springjack()
        rishada = Rishada(springjack)
        market = Market(rishada)

        stock = Stock()
        stock.save()

        # Establish external market price
        emp = ExternalMarketPrice()
        emp.price = ext_market_price
        emp.stock = stock
        emp.save()

        # SELLER
        seller = Participant()
        seller.name = 'Margo'
        seller.save()

        # Setup the seller account with some money
        saccount = rishada.create_account(seller.id)

        sile = LedgerEntry()
        sile.account = saccount
        sile.amount = seller_init_funds
        sile.other_memo = 'starting balance'
        sile.txid = 'fakedit0'
        sile.save()

        self.assertEquals(rishada.get_balance(saccount.get_account_id()), seller_init_funds)

        inv = Inventory()
        inv.owner = seller
        inv.stock = stock
        inv.value = .5
        inv.save()

        sell = SellOrder()
        sell.seller = seller
        sell.inventory = inv
        sell.order_type = SellOrder.MARKET_ORDER
        # this essentially places the order in the market
        sell.save()
        sell = SellOrder.objects.get(pk=sell.id)

        # BUYER
        buyer = Participant()
        buyer.name = 'Wilhem'
        buyer.save()

        # Setup the buyer account with some money
        baccount = rishada.create_account(buyer.id)

        bile = LedgerEntry()
        bile.account = baccount
        bile.amount = buyer_init_funds
        bile.other_memo = 'buyer starting balance'
        bile.txid = 'fakedit1'
        bile.save()

        self.assertEquals(rishada.get_balance(baccount.get_account_id()), buyer_init_funds)

        buy = BuyOrder()
        buy.buyer = buyer
        buy.stock = stock
        buy.order_type = BuyOrder.LIMIT_ORDER
        buy.price = buy_price
        # this essentially places the order in the market
        buy.save()
        buy = BuyOrder.objects.get(pk=buy.id)

        # Test market
        self.assertEquals(market.current_market_price(stock), ext_market_price)

        # seller should have 1 item of this stock in inventory.
        self.assertEquals(Inventory.manager.count(seller, stock), 1)
        # buyer should have none.
        self.assertEquals(Inventory.manager.count(buyer, stock), 0)

        # Connect buyers and sellers
        market.clear_market()

        # Check to make sure no money has entered or left the system
        cur_economy = LedgerEntry.objects.all().aggregate(Sum('amount'))['amount__sum']
        self.assertEquals(cur_economy, base_economy)

        # TEST that clear_market() made the right transaction
        xaction_count = Transaction.objects.all().count()
        xactions = Transaction.objects.filter(buy_order=buy)
        self.assertEquals(xactions.count(), 0)

        # seller should still have inventory.
        self.assertEquals(Inventory.manager.count(seller, stock), 1)

        # buyer doesn't have it.
        self.assertEquals(Inventory.manager.count(buyer, stock), 0)

        # seller inventory should remain available
        inv = Inventory.objects.get(pk=inv.id)
        self.assertEquals(inv.status, Inventory.AVAILABLE_STATUS)

        # seller still has same account balance
        self.assertEquals(rishada.get_balance(saccount.get_account_id()), seller_init_funds)

        # but buyer still has same account balance
        self.assertEquals(rishada.get_balance(baccount.get_account_id()), buyer_init_funds)

        # and market price should be unchanged - the external market price.
        self.assertEquals(market.current_market_price(stock), ext_market_price)

        # Check to make sure no money has entered or left the system
        cur_economy = LedgerEntry.objects.all().aggregate(Sum('amount'))['amount__sum']
        self.assertEquals(cur_economy, base_economy)

    """ One Buyer, one Seller, one stock
    Buyer does have sufficient funds
    BuyOrder is LIMIT
    SellOrder is MARKET
    Orders must match... therefor...

    THIS CASE DOES NOT EXIST. There will always be a match if one
    order is LIMIT and the other is MARKET
    """

    def test_clear_market_b_lim_funded_s_mark_nomatch(self):
        self.assertTrue(True)

    """ One Buyer, one Seller, one stock
    Buyer does not have sufficient funds
    BuyOrder is LIMIT
    SellOrder is MARKET
    Orders match but insufficient funds, no transaction

    THIS CASE DOES NOT EXIST. There will always be a match if one
    order is LIMIT and the other is MARKET

    same case as test_clear_market_b_lim_unfunded_s_mark_match()
    """

    def test_clear_market_b_lim_unfunded_s_mark_nomatch(self):
        self.assertTrue(True)

    """ One Buyer, one Seller, one stock
    Buyer has sufficient funds
    BuyOrder is LIMIT
    SellOrder is LIMIT
    Orders match, transaction results
    order ships and buyer confirms
    """

    def test_clear_market_b_lim_funded_s_lim_match(self):
        seller_init_funds = 1.75
        # FUNDED
        buyer_init_funds = 3.0
        buy_price = .4875
        sell_price = .46

        escrow_owner = Participant.objects.filter(name='HoodwinkEscrowOfficer').first()

        base_economy = seller_init_funds + buyer_init_funds

        springjack = Springjack()
        rishada = Rishada(springjack)
        market = Market(rishada)

        stock = Stock()
        stock.save()

        # SELLER
        seller = Participant()
        seller.name = 'Margo'
        seller.save()

        # Setup the seller account with some money
        saccount = rishada.create_account(seller.id)

        sile = LedgerEntry()
        sile.account = saccount
        sile.amount = seller_init_funds
        sile.other_memo = 'starting balance'
        sile.txid = 'fakedit0'
        sile.save()

        self.assertEquals(rishada.get_balance(saccount.get_account_id()), seller_init_funds)

        inv = Inventory()
        inv.owner = seller
        inv.stock = stock
        inv.value = .5
        inv.save()

        sell = SellOrder()
        sell.seller = seller
        sell.inventory = inv
        sell.order_type = SellOrder.LIMIT_ORDER
        sell.price = sell_price
        # this essentially places the order in the market
        sell.save()
        sell = SellOrder.objects.get(pk=sell.id)

        # BUYER
        buyer = Participant()
        buyer.name = 'Wilhem'
        buyer.save()

        # Setup the buyer account with some money
        baccount = rishada.create_account(buyer.id)

        bile = LedgerEntry()
        bile.account = baccount
        bile.amount = buyer_init_funds
        bile.other_memo = 'buyer starting balance'
        bile.txid = 'fakedit1'
        bile.save()

        self.assertEquals(rishada.get_balance(baccount.get_account_id()), buyer_init_funds)

        buy = BuyOrder()
        buy.buyer = buyer
        buy.stock = stock
        buy.order_type = BuyOrder.LIMIT_ORDER
        buy.price = buy_price
        # this essentially places the order in the market
        buy.save()
        buy = BuyOrder.objects.get(pk=buy.id)

        # seller should have 1 item of this stock in inventory.
        self.assertEquals(Inventory.manager.count(seller, stock), 1)
        # buyer should have none.
        self.assertEquals(Inventory.manager.count(buyer, stock), 0)

        # Connect buyers and sellers
        market.clear_market()

        # Check to make sure no money has entered or left the system
        cur_economy = LedgerEntry.objects.all().aggregate(Sum('amount'))['amount__sum']
        self.assertEquals(cur_economy, base_economy)

        # TEST that clear_market() made the right transaction
        xaction_count = Transaction.objects.all().count()
        xactions = Transaction.objects.filter(buy_order=buy)
        self.assertEquals(xactions.count(), 1)
        xaction = xactions[0]
        self.assertEquals(xaction, buy.get_transaction())
        self.assertEquals(xaction.buy_order.id, buy.id)
        self.assertEquals(xaction.sell_order.id, sell.id)
        self.assertEquals(xaction.price, sell_price)

        self.assertLessEqual(xaction.initiated_datetime, timezone.now())
        self.assertIsNone(xaction.shipped_datetime)
        self.assertIsNone(xaction.completed_datetime)

        # seller should have reduced inventory.
        self.assertEquals(Inventory.manager.count(seller, stock), 0)

        # buyer doesn't have it yet...
        self.assertEquals(Inventory.manager.count(buyer, stock), 0)

        # seller inventory should be statused as sold
        inv = Inventory.objects.get(pk=inv.id)
        self.assertEquals(inv.status, Inventory.SOLD_STATUS)

        # seller does not have funds yet - they are in escrow
        self.assertEquals(rishada.get_balance(saccount.get_account_id()), seller_init_funds)

        # but buyer is out the money
        self.assertEquals(rishada.get_balance(baccount.get_account_id()), buyer_init_funds - sell_price)

        # and market price should be updated.
        self.assertEquals(market.current_market_price(stock), sell_price)

        # one last check to make sure that clearing the market again doesn't dup any transactions
        market.clear_market()
        self.assertEquals(Transaction.objects.all().count(), xaction_count)
        self.assertEquals(market.current_market_price(stock), sell_price)

        # seller ships it
        xaction.ship()

        # buyer gets it!
        xaction.close()

        # yay, the buyer got their goods!
        rishada.release_escrow(rishada.get_account_by_participant_id(xaction.sell_order.seller.id).get_account_id(), xaction.id)

        # seller inventory should be statused as delivered
        inv = Inventory.objects.get(pk=inv.id)
        self.assertEquals(inv.status, Inventory.DELIVERED_STATUS)

        # buyer is still out the money
        self.assertEquals(rishada.get_balance(baccount.get_account_id()), buyer_init_funds - sell_price)

        # seller has his money!
        self.assertEquals(rishada.get_balance(saccount.get_account_id()), seller_init_funds + sell_price)

        # and market price should now be the buy_price
        self.assertEquals(market.current_market_price(stock), sell_price)

        # buyer should have some inventory...
        binv = Inventory.objects.filter(owner=buyer).first()
        self.assertEquals(binv.value, sell_price)

        # Check to make sure no money has entered or left the system
        cur_economy = LedgerEntry.objects.all().aggregate(Sum('amount'))['amount__sum']
        self.assertEquals(cur_economy, base_economy)

    """ One Buyer, one Seller, one stock
    Buyer has sufficient funds
    BuyOrder is LIMIT
    SellOrder is LIMIT
    Orders do not match because of price, no transaction
    an external market price exists
    """

    def test_clear_market_b_lim_funded_s_lim_nomatch_with_ext_market_price(self):
        seller_init_funds = 1.75
        # FUNDED
        buyer_init_funds = 3.0
        buy_price = .4875
        sell_price = .53
        ext_market_price = 0.5

        escrow_owner = Participant.objects.filter(name='HoodwinkEscrowOfficer').first()

        base_economy = seller_init_funds + buyer_init_funds

        springjack = Springjack()
        rishada = Rishada(springjack)
        market = Market(rishada)

        stock = Stock()
        stock.save()

        # Establish external market price
        emp = ExternalMarketPrice()
        emp.price = ext_market_price
        emp.stock = stock
        emp.save()

        # SELLER
        seller = Participant()
        seller.name = 'Margo'
        seller.save()

        # Setup the seller account with some money
        saccount = rishada.create_account(seller.id)

        sile = LedgerEntry()
        sile.account = saccount
        sile.amount = seller_init_funds
        sile.other_memo = 'starting balance'
        sile.txid = 'fakedit0'
        sile.save()

        self.assertEquals(rishada.get_balance(saccount.get_account_id()), seller_init_funds)

        inv = Inventory()
        inv.owner = seller
        inv.stock = stock
        inv.value = .5
        inv.save()

        sell = SellOrder()
        sell.seller = seller
        sell.inventory = inv
        sell.order_type = SellOrder.LIMIT_ORDER
        sell.price = sell_price
        # this essentially places the order in the market
        sell.save()
        sell = SellOrder.objects.get(pk=sell.id)

        # BUYER
        buyer = Participant()
        buyer.name = 'Wilhem'
        buyer.save()

        # Setup the buyer account with some money
        baccount = rishada.create_account(buyer.id)

        bile = LedgerEntry()
        bile.account = baccount
        bile.amount = buyer_init_funds
        bile.other_memo = 'buyer starting balance'
        bile.txid = 'fakedit1'
        bile.save()

        self.assertEquals(rishada.get_balance(baccount.get_account_id()), buyer_init_funds)

        buy = BuyOrder()
        buy.buyer = buyer
        buy.stock = stock
        buy.order_type = BuyOrder.LIMIT_ORDER
        buy.price = buy_price
        # this essentially places the order in the market
        buy.save()
        buy = BuyOrder.objects.get(pk=buy.id)

        # Test market
        self.assertEquals(market.current_market_price(stock), ext_market_price)

        # seller should have 1 item of this stock in inventory.
        self.assertEquals(Inventory.manager.count(seller, stock), 1)
        # buyer should have none.
        self.assertEquals(Inventory.manager.count(buyer, stock), 0)

        # Connect buyers and sellers
        market.clear_market()

        # Check to make sure no money has entered or left the system
        cur_economy = LedgerEntry.objects.all().aggregate(Sum('amount'))['amount__sum']
        self.assertEquals(cur_economy, base_economy)

        # TEST that clear_market() made the right transaction
        xaction_count = Transaction.objects.all().count()
        xactions = Transaction.objects.filter(buy_order=buy)
        self.assertEquals(xactions.count(), 0)

        # seller should have same inventory.
        self.assertEquals(Inventory.manager.count(seller, stock), 1)

        # buyer doesn't have it.
        self.assertEquals(Inventory.manager.count(buyer, stock), 0)

        # seller inventory should stay as available
        inv = Inventory.objects.get(pk=inv.id)
        self.assertEquals(inv.status, Inventory.AVAILABLE_STATUS)

        # seller has same account balance
        self.assertEquals(rishada.get_balance(saccount.get_account_id()), seller_init_funds)

        # buyer has same account balance
        self.assertEquals(rishada.get_balance(baccount.get_account_id()), buyer_init_funds)

        # and market price stays the same
        self.assertEquals(market.current_market_price(stock), ext_market_price)

        # Check to make sure no money has entered or left the system
        cur_economy = LedgerEntry.objects.all().aggregate(Sum('amount'))['amount__sum']
        self.assertEquals(cur_economy, base_economy)

    """ One Buyer, one Seller, one stock
    Buyer does not have sufficient funds
    BuyOrder is LIMIT
    SellOrder is LIMIT
    Orders match but insufficient funds, no transaction
    external market price exists
    """

    def test_clear_market_b_lim_unfunded_s_lim_match(self):
        seller_init_funds = 1.75
        # UNFUNDED
        buyer_init_funds = 0.313131
        buy_price = .4875
        sell_price = .487
        ext_market_price = 0.49

        escrow_owner = Participant.objects.filter(name='HoodwinkEscrowOfficer').first()

        base_economy = seller_init_funds + buyer_init_funds

        springjack = Springjack()
        rishada = Rishada(springjack)
        market = Market(rishada)

        stock = Stock()
        stock.save()

        # Establish external market price
        emp = ExternalMarketPrice()
        emp.price = ext_market_price
        emp.stock = stock
        emp.save()

        # SELLER
        seller = Participant()
        seller.name = 'Margo'
        seller.save()

        # Setup the seller account with some money
        saccount = rishada.create_account(seller.id)

        sile = LedgerEntry()
        sile.account = saccount
        sile.amount = seller_init_funds
        sile.other_memo = 'starting balance'
        sile.txid = 'fakedit0'
        sile.save()

        self.assertEquals(rishada.get_balance(saccount.get_account_id()), seller_init_funds)

        inv = Inventory()
        inv.owner = seller
        inv.stock = stock
        inv.value = .5
        inv.save()

        sell = SellOrder()
        sell.seller = seller
        sell.inventory = inv
        sell.order_type = SellOrder.LIMIT_ORDER
        sell.price = sell_price
        # this essentially places the order in the market
        sell.save()
        sell = SellOrder.objects.get(pk=sell.id)

        # BUYER
        buyer = Participant()
        buyer.name = 'Wilhem'
        buyer.save()

        # Setup the buyer account with some money
        baccount = rishada.create_account(buyer.id)

        bile = LedgerEntry()
        bile.account = baccount
        bile.amount = buyer_init_funds
        bile.other_memo = 'buyer starting balance'
        bile.txid = 'fakedit1'
        bile.save()

        self.assertEquals(rishada.get_balance(baccount.get_account_id()), buyer_init_funds)

        buy = BuyOrder()
        buy.buyer = buyer
        buy.stock = stock
        buy.order_type = BuyOrder.LIMIT_ORDER
        buy.price = buy_price
        # this essentially places the order in the market
        buy.save()
        buy = BuyOrder.objects.get(pk=buy.id)

        # Test market
        self.assertEquals(market.current_market_price(stock), ext_market_price)

        # seller should have 1 item of this stock in inventory.
        self.assertEquals(Inventory.manager.count(seller, stock), 1)
        # buyer should have none.
        self.assertEquals(Inventory.manager.count(buyer, stock), 0)

        # Connect buyers and sellers
        market.clear_market()

        # Check to make sure no money has entered or left the system
        cur_economy = LedgerEntry.objects.all().aggregate(Sum('amount'))['amount__sum']
        self.assertEquals(cur_economy, base_economy)

        # TEST that clear_market() made the right transaction
        xaction_count = Transaction.objects.all().count()
        xactions = Transaction.objects.filter(buy_order=buy)
        self.assertEquals(xactions.count(), 0)

        # seller should still have inventory.
        self.assertEquals(Inventory.manager.count(seller, stock), 1)

        # buyer doesn't have it.
        self.assertEquals(Inventory.manager.count(buyer, stock), 0)

        # seller inventory should remain available
        inv = Inventory.objects.get(pk=inv.id)
        self.assertEquals(inv.status, Inventory.AVAILABLE_STATUS)

        # seller still has same account balance
        self.assertEquals(rishada.get_balance(saccount.get_account_id()), seller_init_funds)

        # but buyer still has same account balance
        self.assertEquals(rishada.get_balance(baccount.get_account_id()), buyer_init_funds)

        # and market price should be unchanged - the external market price.
        self.assertEquals(market.current_market_price(stock), ext_market_price)

        # Check to make sure no money has entered or left the system
        cur_economy = LedgerEntry.objects.all().aggregate(Sum('amount'))['amount__sum']
        self.assertEquals(cur_economy, base_economy)

    """ One Buyer, one Seller, one stock
    Buyer does not have sufficient funds
    BuyOrder is LIMIT
    SellOrder is LIMIT
    Orders match but insufficient funds, no transaction
    external market price exists
    """

    def test_clear_market_b_lim_unfunded_s_lim_nomatch(self):
        seller_init_funds = 1.75
        # UNFUNDED
        buyer_init_funds = 0.313131
        buy_price = .4875
        sell_price = .52
        ext_market_price = 0.49

        escrow_owner = Participant.objects.filter(name='HoodwinkEscrowOfficer').first()

        base_economy = seller_init_funds + buyer_init_funds

        springjack = Springjack()
        rishada = Rishada(springjack)
        market = Market(rishada)

        stock = Stock()
        stock.save()

        # Establish external market price
        emp = ExternalMarketPrice()
        emp.price = ext_market_price
        emp.stock = stock
        emp.save()

        # SELLER
        seller = Participant()
        seller.name = 'Margo'
        seller.save()

        # Setup the seller account with some money
        saccount = rishada.create_account(seller.id)

        sile = LedgerEntry()
        sile.account = saccount
        sile.amount = seller_init_funds
        sile.other_memo = 'starting balance'
        sile.txid = 'fakedit0'
        sile.save()

        self.assertEquals(rishada.get_balance(saccount.get_account_id()), seller_init_funds)

        inv = Inventory()
        inv.owner = seller
        inv.stock = stock
        inv.value = .5
        inv.save()

        sell = SellOrder()
        sell.seller = seller
        sell.inventory = inv
        sell.order_type = SellOrder.LIMIT_ORDER
        sell.price = sell_price
        # this essentially places the order in the market
        sell.save()
        sell = SellOrder.objects.get(pk=sell.id)

        # BUYER
        buyer = Participant()
        buyer.name = 'Wilhem'
        buyer.save()

        # Setup the buyer account with some money
        baccount = rishada.create_account(buyer.id)

        bile = LedgerEntry()
        bile.account = baccount
        bile.amount = buyer_init_funds
        bile.other_memo = 'buyer starting balance'
        bile.txid = 'fakedit1'
        bile.save()

        self.assertEquals(rishada.get_balance(baccount.get_account_id()), buyer_init_funds)

        buy = BuyOrder()
        buy.buyer = buyer
        buy.stock = stock
        buy.order_type = BuyOrder.LIMIT_ORDER
        buy.price = buy_price
        # this essentially places the order in the market
        buy.save()
        buy = BuyOrder.objects.get(pk=buy.id)

        # Test market
        self.assertEquals(market.current_market_price(stock), ext_market_price)

        # seller should have 1 item of this stock in inventory.
        self.assertEquals(Inventory.manager.count(seller, stock), 1)
        # buyer should have none.
        self.assertEquals(Inventory.manager.count(buyer, stock), 0)

        # Connect buyers and sellers
        market.clear_market()

        # Check to make sure no money has entered or left the system
        cur_economy = LedgerEntry.objects.all().aggregate(Sum('amount'))['amount__sum']
        self.assertEquals(cur_economy, base_economy)

        # TEST that clear_market() made the right transaction
        xaction_count = Transaction.objects.all().count()
        xactions = Transaction.objects.filter(buy_order=buy)
        self.assertEquals(xactions.count(), 0)

        # seller should still have inventory.
        self.assertEquals(Inventory.manager.count(seller, stock), 1)

        # buyer doesn't have it.
        self.assertEquals(Inventory.manager.count(buyer, stock), 0)

        # seller inventory should remain available
        inv = Inventory.objects.get(pk=inv.id)
        self.assertEquals(inv.status, Inventory.AVAILABLE_STATUS)

        # seller still has same account balance
        self.assertEquals(rishada.get_balance(saccount.get_account_id()), seller_init_funds)

        # but buyer still has same account balance
        self.assertEquals(rishada.get_balance(baccount.get_account_id()), buyer_init_funds)

        # and market price should be unchanged - the external market price.
        self.assertEquals(market.current_market_price(stock), ext_market_price)

        # Check to make sure no money has entered or left the system
        cur_economy = LedgerEntry.objects.all().aggregate(Sum('amount'))['amount__sum']
        self.assertEquals(cur_economy, base_economy)

    """ One Buyer, one Seller, one stock
    Buyer has sufficient funds
    BuyOrder is MARKET
    SellOrder is LIMIT
    Orders match, transaction results
    order ships and buyer confirms
    """

    def test_clear_market_b_mark_funded_s_lim_match(self):
        seller_init_funds = 1.75
        # FUNDED
        buyer_init_funds = 3.0
        sell_price = .46

        escrow_owner = Participant.objects.filter(name='HoodwinkEscrowOfficer').first()

        base_economy = seller_init_funds + buyer_init_funds

        springjack = Springjack()
        rishada = Rishada(springjack)
        market = Market(rishada)

        stock = Stock()
        stock.save()

        # SELLER
        seller = Participant()
        seller.name = 'Margo'
        seller.save()

        # Setup the seller account with some money
        saccount = rishada.create_account(seller.id)

        sile = LedgerEntry()
        sile.account = saccount
        sile.amount = seller_init_funds
        sile.other_memo = 'starting balance'
        sile.txid = 'fakedit0'
        sile.save()

        self.assertEquals(rishada.get_balance(saccount.get_account_id()), seller_init_funds)

        inv = Inventory()
        inv.owner = seller
        inv.stock = stock
        inv.value = .5
        inv.save()

        sell = SellOrder()
        sell.seller = seller
        sell.inventory = inv
        sell.order_type = SellOrder.LIMIT_ORDER
        sell.price = sell_price
        # this essentially places the order in the market
        sell.save()
        sell = SellOrder.objects.get(pk=sell.id)

        # BUYER
        buyer = Participant()
        buyer.name = 'Wilhem'
        buyer.save()

        # Setup the buyer account with some money
        baccount = rishada.create_account(buyer.id)

        bile = LedgerEntry()
        bile.account = baccount
        bile.amount = buyer_init_funds
        bile.other_memo = 'buyer starting balance'
        bile.txid = 'fakedit1'
        bile.save()

        self.assertEquals(rishada.get_balance(baccount.get_account_id()), buyer_init_funds)

        buy = BuyOrder()
        buy.buyer = buyer
        buy.stock = stock
        buy.order_type = BuyOrder.MARKET_ORDER
        # this essentially places the order in the market
        buy.save()
        buy = BuyOrder.objects.get(pk=buy.id)

        # seller should have 1 item of this stock in inventory.
        self.assertEquals(Inventory.manager.count(seller, stock), 1)
        # buyer should have none.
        self.assertEquals(Inventory.manager.count(buyer, stock), 0)

        # Connect buyers and sellers
        market.clear_market()

        # Check to make sure no money has entered or left the system
        cur_economy = LedgerEntry.objects.all().aggregate(Sum('amount'))['amount__sum']
        self.assertEquals(cur_economy, base_economy)

        # TEST that clear_market() made the right transaction
        xaction_count = Transaction.objects.all().count()
        xactions = Transaction.objects.filter(buy_order=buy)
        self.assertEquals(xactions.count(), 1)
        xaction = xactions[0]
        self.assertEquals(xaction, buy.get_transaction())
        self.assertEquals(xaction.buy_order.id, buy.id)
        self.assertEquals(xaction.sell_order.id, sell.id)
        self.assertEquals(xaction.price, sell_price)

        self.assertLessEqual(xaction.initiated_datetime, timezone.now())
        self.assertIsNone(xaction.shipped_datetime)
        self.assertIsNone(xaction.completed_datetime)

        # seller should have reduced inventory.
        self.assertEquals(Inventory.manager.count(seller, stock), 0)

        # buyer doesn't have it yet...
        self.assertEquals(Inventory.manager.count(buyer, stock), 0)

        # seller inventory should be statused as sold
        inv = Inventory.objects.get(pk=inv.id)
        self.assertEquals(inv.status, Inventory.SOLD_STATUS)

        # seller does not have funds yet - they are in escrow
        self.assertEquals(rishada.get_balance(saccount.get_account_id()), seller_init_funds)

        # but buyer is out the money
        self.assertEquals(rishada.get_balance(baccount.get_account_id()), buyer_init_funds - sell_price)

        # and market price should be updated.
        self.assertEquals(market.current_market_price(stock), sell_price)

        # one last check to make sure that clearing the market again doesn't dup any transactions
        market.clear_market()
        self.assertEquals(Transaction.objects.all().count(), xaction_count)
        self.assertEquals(market.current_market_price(stock), sell_price)

        # seller ships it
        xaction.ship()

        # buyer gets it!
        xaction.close()

        # yay, the buyer got their goods!
        rishada.release_escrow(rishada.get_account_by_participant_id(xaction.sell_order.seller.id).get_account_id(), xaction.id)

        # seller inventory should be statused as delivered
        inv = Inventory.objects.get(pk=inv.id)
        self.assertEquals(inv.status, Inventory.DELIVERED_STATUS)

        # buyer is still out the money
        self.assertEquals(rishada.get_balance(baccount.get_account_id()), buyer_init_funds - sell_price)

        # seller has his money!
        self.assertEquals(rishada.get_balance(saccount.get_account_id()), seller_init_funds + sell_price)

        # and market price should now be the sell_price
        self.assertEquals(market.current_market_price(stock), sell_price)

        # buyer should have some inventory...
        binv = Inventory.objects.filter(owner=buyer).first()
        self.assertEquals(binv.value, sell_price)

        # Check to make sure no money has entered or left the system
        cur_economy = LedgerEntry.objects.all().aggregate(Sum('amount'))['amount__sum']
        self.assertEquals(cur_economy, base_economy)

    """ This is not a scenario that can happen. If the Buyer is buying
    at Market price, then he will buy at whatever the lowest seller
    price is, which would create a match.
    """

    def test_clear_market_b_mark_funded_s_lim_nomatch(self):
        self.assertTrue(True)

    """ One Buyer, one Seller, one stock
    Buyer does not have sufficient funds
    BuyOrder is MARKET
    SellOrder is LIMIT
    Orders match, but no transaction
    """

    def test_clear_market_b_mark_unfunded_s_lim_match(self):
        seller_init_funds = 1.75
        # UNFUNDED
        buyer_init_funds = .2
        sell_price = .46

        escrow_owner = Participant.objects.filter(name='HoodwinkEscrowOfficer').first()

        base_economy = seller_init_funds + buyer_init_funds

        springjack = Springjack()
        rishada = Rishada(springjack)
        market = Market(rishada)

        stock = Stock()
        stock.save()

        # SELLER
        seller = Participant()
        seller.name = 'Margo'
        seller.save()

        # Setup the seller account with some money
        saccount = rishada.create_account(seller.id)

        sile = LedgerEntry()
        sile.account = saccount
        sile.amount = seller_init_funds
        sile.other_memo = 'starting balance'
        sile.txid = 'fakedit0'
        sile.save()

        self.assertEquals(rishada.get_balance(saccount.get_account_id()), seller_init_funds)

        inv = Inventory()
        inv.owner = seller
        inv.stock = stock
        inv.value = .5
        inv.save()

        sell = SellOrder()
        sell.seller = seller
        sell.inventory = inv
        sell.order_type = SellOrder.LIMIT_ORDER
        sell.price = sell_price
        # this essentially places the order in the market
        sell.save()
        sell = SellOrder.objects.get(pk=sell.id)

        # BUYER
        buyer = Participant()
        buyer.name = 'Wilhem'
        buyer.save()

        # Setup the buyer account with some money
        baccount = rishada.create_account(buyer.id)

        bile = LedgerEntry()
        bile.account = baccount
        bile.amount = buyer_init_funds
        bile.other_memo = 'buyer starting balance'
        bile.txid = 'fakedit1'
        bile.save()

        self.assertEquals(rishada.get_balance(baccount.get_account_id()), buyer_init_funds)

        buy = BuyOrder()
        buy.buyer = buyer
        buy.stock = stock
        buy.order_type = BuyOrder.MARKET_ORDER
        # this essentially places the order in the market
        buy.save()
        buy = BuyOrder.objects.get(pk=buy.id)

        # seller should have 1 item of this stock in inventory.
        self.assertEquals(Inventory.manager.count(seller, stock), 1)
        # buyer should have none.
        self.assertEquals(Inventory.manager.count(buyer, stock), 0)

        # Connect buyers and sellers
        market.clear_market()

        # Check to make sure no money has entered or left the system
        cur_economy = LedgerEntry.objects.all().aggregate(Sum('amount'))['amount__sum']
        self.assertEquals(cur_economy, base_economy)

        # TEST that clear_market() made the right transaction
        xaction_count = Transaction.objects.all().count()
        xactions = Transaction.objects.filter(buy_order=buy)
        self.assertEquals(xactions.count(), 0)

        # seller should still have inventory.
        self.assertEquals(Inventory.manager.count(seller, stock), 1)

        # buyer doesn't have it.
        self.assertEquals(Inventory.manager.count(buyer, stock), 0)

        # seller inventory should remain available
        inv = Inventory.objects.get(pk=inv.id)
        self.assertEquals(inv.status, Inventory.AVAILABLE_STATUS)

        # seller still has same account balance
        self.assertEquals(rishada.get_balance(saccount.get_account_id()), seller_init_funds)

        # but buyer still has same account balance
        self.assertEquals(rishada.get_balance(baccount.get_account_id()), buyer_init_funds)

        # Check to make sure no money has entered or left the system
        cur_economy = LedgerEntry.objects.all().aggregate(Sum('amount'))['amount__sum']
        self.assertEquals(cur_economy, base_economy)

    """ When there is an order at market, there is always a match. So
    this case isn't possible.
    """

    def test_clear_market_b_mark_unfunded_s_lim_nomatch(self):
        self.assertTrue(True)


class MultiTestCases(TestCase):

    def setup_person(self, rishada, name, balance):
        player = Participant()
        player.name = name
        player.save()
        acct = rishada.create_account(player.id)
        sile = LedgerEntry()
        sile.account = acct
        sile.amount = balance
        sile.other_memo = 'starting balance'
        sile.txid = 'fakedit' + str(uuid.uuid4())
        sile.save()
        return player

    def setup_accounts(self):
        self.escrow_owner = Participant.objects.filter(name='HoodwinkEscrowOfficer').first()

        self.stock_a = Stock()
        self.stock_a.save()
        self.stock_b = Stock()
        self.stock_b.save()

        # SELLERS
        sally_starting_balance = 10
        self.sally = self.setup_person(self.rishada, 'Sally', sally_starting_balance)
        self.sally_inv = Inventory()
        self.sally_inv.owner = self.sally
        self.sally_inv.stock = self.stock_a
        self.sally_inv.value = .5
        self.sally_inv.save()

        sam_starting_balance = 11
        self.sam = self.setup_person(self.rishada, 'Sam', sam_starting_balance)
        self.sam_inv = Inventory()
        self.sam_inv.owner = self.sam
        self.sam_inv.stock = self.stock_a
        self.sam_inv.value = .5
        self.sam_inv.save()

        steve_starting_balance = 12
        self.steve = self.setup_person(self.rishada, 'Steve', steve_starting_balance)
        self.steve_inv = Inventory()
        self.steve_inv.owner = self.steve
        self.steve_inv.stock = self.stock_a
        self.steve_inv.value = .5
        self.steve_inv.save()

        stuart_starting_balance = 13
        self.stuart = self.setup_person(self.rishada, 'Stuart', stuart_starting_balance)
        self.stuart_inv = Inventory()
        self.stuart_inv.owner = self.stuart
        self.stuart_inv.stock = self.stock_a
        self.stuart_inv.value = .5
        self.stuart_inv.save()

        sid_starting_balance = 14
        self.sid = self.setup_person(self.rishada, 'Sid', sid_starting_balance)
        self.sid_inv = Inventory()
        self.sid_inv.owner = self.sid
        self.sid_inv.stock = self.stock_a
        self.sid_inv.value = .5
        self.sid_inv.save()

        # BUYERS
        bob_starting_balance = 3.33
        self.bob = self.setup_person(self.rishada, 'Bob', bob_starting_balance)

        beau_starting_balance = 5.33
        self.beau = self.setup_person(self.rishada, 'Beau', beau_starting_balance)

        barb_starting_balance = 7.33
        self.barb = self.setup_person(self.rishada, 'Barb', barb_starting_balance)

        betty_starting_balance = 10.33
        self.betty = self.setup_person(self.rishada, 'Betty', betty_starting_balance)

        basil_starting_balance = 13.33
        self.basil = self.setup_person(self.rishada, 'Basil', basil_starting_balance)

        base_economy = sally_starting_balance + sam_starting_balance + steve_starting_balance + stuart_starting_balance + sid_starting_balance + \
            bob_starting_balance + beau_starting_balance + barb_starting_balance + betty_starting_balance + basil_starting_balance
        return base_economy

    def test_clear_market_multiples_0(self):
        springjack = Springjack()
        self.rishada = Rishada(springjack)
        market = Market(self.rishada)

        base_economy = self.setup_accounts()

        # Check to make sure no money has entered or left the system
        cur_economy = LedgerEntry.objects.all().aggregate(Sum('amount'))['amount__sum']
        self.assertAlmostEquals(cur_economy, base_economy, places=7)

        barb_buy = BuyOrder(buyer=self.barb, stock=self.stock_a, order_type=BuyOrder.MARKET_ORDER)
        barb_buy.save()

        bob_buy = BuyOrder(buyer=self.bob, stock=self.stock_a, order_type=BuyOrder.MARKET_ORDER)
        bob_buy.save()

        basil_buy = BuyOrder(buyer=self.basil, stock=self.stock_a, order_type=BuyOrder.LIMIT_ORDER, price=1.25)
        basil_buy.save()

        stuart_sell = SellOrder(seller=self.stuart, inventory=self.stuart_inv, order_type=SellOrder.LIMIT_ORDER, price=1.2)
        stuart_sell.save()

        sam_sell = SellOrder(seller=self.sam, inventory=self.sam_inv, order_type=SellOrder.LIMIT_ORDER, price=1.4)
        sam_sell.save()

        sid_sell = SellOrder(seller=self.sid, inventory=self.sid_inv, order_type=SellOrder.LIMIT_ORDER, price=1.6)
        sid_sell.save()

        # Connect buyers and sellers
        market.clear_market()

        # Check to make sure no money has entered or left the system
        cur_economy = LedgerEntry.objects.all().aggregate(Sum('amount'))['amount__sum']
        self.assertAlmostEquals(cur_economy, base_economy, places=7)

        # 3 sell orders and 3 buy orders. They will be evaluated in the order that they were put in.
        # Barb will win Stuart's sell. Barb's account will move 1.2 to escrow
        # That will set the market price to 1.2
        # Then bob will win Sam's sell. Bob's account will move 1.4 to escrow
        # That will set the market price to 1.4
        # Then Basil's order will look for a deal at 1.25 or below, and not find anything.
        # Sid will sell nothing.

        self.stuart_inv = Inventory.objects.get(pk=self.stuart_inv.id)
        xactions = Transaction.objects.filter(buy_order=barb_buy)
        self.assertEquals(xactions.count(), 1)
        self.assertEquals(self.stuart_inv.status, Inventory.SOLD_STATUS)
        self.assertAlmostEquals(self.rishada.get_account_by_participant_id(self.barb.id).get_balance(), 7.33 - 1.2, places=7)

        self.sam_inv = Inventory.objects.get(pk=self.sam_inv.id)
        xactions = Transaction.objects.filter(buy_order=bob_buy)
        self.assertEquals(xactions.count(), 1)
        self.assertEquals(self.sam_inv.status, Inventory.SOLD_STATUS)
        self.assertAlmostEquals(self.rishada.get_account_by_participant_id(self.bob.id).get_balance(), 3.33 - 1.4, places=7)

        self.sid_inv = Inventory.objects.get(pk=self.sid_inv.id)
        xactions = Transaction.objects.filter(buy_order=basil_buy)
        self.assertEquals(xactions.count(), 0)
        self.assertEquals(self.sid_inv.status, Inventory.AVAILABLE_STATUS)
        self.assertAlmostEquals(self.rishada.get_account_by_participant_id(self.basil.id).get_balance(), 13.33, places=7)

        # Check to make sure no money has entered or left the system
        cur_economy = LedgerEntry.objects.all().aggregate(Sum('amount'))['amount__sum']
        self.assertAlmostEquals(cur_economy, base_economy, places=7)

        # Test market
        self.assertEquals(market.current_market_price(self.stock_a), 1.4)
        self.assertEquals(market.current_bid_price(self.stock_a), 1.25)
        self.assertEquals(market.current_ask_price(self.stock_a), 1.6)

    def test_clear_market_multiples_1(self):
        springjack = Springjack()
        self.rishada = Rishada(springjack)
        market = Market(self.rishada)

        base_economy = self.setup_accounts()

        # Check to make sure no money has entered or left the system
        cur_economy = LedgerEntry.objects.all().aggregate(Sum('amount'))['amount__sum']
        self.assertAlmostEquals(cur_economy, base_economy, places=7)

        barb_buy = BuyOrder(buyer=self.barb, stock=self.stock_a, order_type=BuyOrder.MARKET_ORDER)
        barb_buy.save()

        bob_buy = BuyOrder(buyer=self.bob, stock=self.stock_a, order_type=BuyOrder.MARKET_ORDER)
        bob_buy.save()

        basil_buy = BuyOrder(buyer=self.basil, stock=self.stock_a, order_type=BuyOrder.LIMIT_ORDER, price=1.25)
        basil_buy.save()

        # Sellers enter market in different order than in test _1. Results should be the same, though.
        sid_sell = SellOrder(seller=self.sid, inventory=self.sid_inv, order_type=SellOrder.LIMIT_ORDER, price=1.6)
        sid_sell.save()

        sam_sell = SellOrder(seller=self.sam, inventory=self.sam_inv, order_type=SellOrder.LIMIT_ORDER, price=1.4)
        sam_sell.save()

        stuart_sell = SellOrder(seller=self.stuart, inventory=self.stuart_inv, order_type=SellOrder.LIMIT_ORDER, price=1.2)
        stuart_sell.save()

        # Connect buyers and sellers
        market.clear_market()

        # Check to make sure no money has entered or left the system
        cur_economy = LedgerEntry.objects.all().aggregate(Sum('amount'))['amount__sum']
        self.assertAlmostEquals(cur_economy, base_economy, places=7)

        # 3 sell orders and 3 buy orders. They will be evaluated in the order that they were put in.
        # Barb will win Stuart's sell. Barb's account will move 1.2 to escrow
        # That will set the market price to 1.2
        # Then bob will win Sam's sell. Bob's account will move 1.4 to escrow
        # That will set the market price to 1.4
        # Then Basil's order will look for a deal at 1.25 or below, and not find anything.
        # Sid will sell nothing.

        self.stuart_inv = Inventory.objects.get(pk=self.stuart_inv.id)
        xactions = Transaction.objects.filter(buy_order=barb_buy)
        self.assertEquals(xactions.count(), 1)
        self.assertEquals(self.stuart_inv.status, Inventory.SOLD_STATUS)
        self.assertAlmostEquals(self.rishada.get_account_by_participant_id(self.barb.id).get_balance(), 7.33 - 1.2, places=7)

        self.sam_inv = Inventory.objects.get(pk=self.sam_inv.id)
        xactions = Transaction.objects.filter(buy_order=bob_buy)
        self.assertEquals(xactions.count(), 1)
        self.assertEquals(self.sam_inv.status, Inventory.SOLD_STATUS)
        self.assertAlmostEquals(self.rishada.get_account_by_participant_id(self.bob.id).get_balance(), 3.33 - 1.4, places=7)

        self.sid_inv = Inventory.objects.get(pk=self.sid_inv.id)
        xactions = Transaction.objects.filter(buy_order=basil_buy)
        self.assertEquals(xactions.count(), 0)
        self.assertEquals(self.sid_inv.status, Inventory.AVAILABLE_STATUS)
        self.assertAlmostEquals(self.rishada.get_account_by_participant_id(self.basil.id).get_balance(), 13.33, places=7)

        # Check to make sure no money has entered or left the system
        cur_economy = LedgerEntry.objects.all().aggregate(Sum('amount'))['amount__sum']
        self.assertAlmostEquals(cur_economy, base_economy, places=7)

        # Test market
        self.assertEquals(market.current_market_price(self.stock_a), 1.4)
        self.assertEquals(market.current_bid_price(self.stock_a), 1.25)
        self.assertEquals(market.current_ask_price(self.stock_a), 1.6)

    def test_clear_market_multiples_2(self):
        springjack = Springjack()
        self.rishada = Rishada(springjack)
        market = Market(self.rishada)

        base_economy = self.setup_accounts()

        # Check to make sure no money has entered or left the system
        cur_economy = LedgerEntry.objects.all().aggregate(Sum('amount'))['amount__sum']
        self.assertAlmostEquals(cur_economy, base_economy, places=7)

        # Now buyers enter the market in a different order. This will change the outcome!
        basil_buy = BuyOrder(buyer=self.basil, stock=self.stock_a, order_type=BuyOrder.LIMIT_ORDER, price=1.25)
        basil_buy.save()

        bob_buy = BuyOrder(buyer=self.bob, stock=self.stock_a, order_type=BuyOrder.MARKET_ORDER)
        bob_buy.save()

        barb_buy = BuyOrder(buyer=self.barb, stock=self.stock_a, order_type=BuyOrder.MARKET_ORDER)
        barb_buy.save()

        stuart_sell = SellOrder(seller=self.stuart, inventory=self.stuart_inv, order_type=SellOrder.LIMIT_ORDER, price=1.2)
        stuart_sell.save()

        sam_sell = SellOrder(seller=self.sam, inventory=self.sam_inv, order_type=SellOrder.LIMIT_ORDER, price=1.4)
        sam_sell.save()

        sid_sell = SellOrder(seller=self.sid, inventory=self.sid_inv, order_type=SellOrder.LIMIT_ORDER, price=1.6)
        sid_sell.save()

        # Connect buyers and sellers
        market.clear_market()

        # Check to make sure no money has entered or left the system
        cur_economy = LedgerEntry.objects.all().aggregate(Sum('amount'))['amount__sum']
        self.assertAlmostEquals(cur_economy, base_economy, places=7)

        # 3 sell orders and 3 buy orders. They will be evaluated in the order that they were put in.
        # Basil's limit order will match Stuart's sell. Basil's account will move 1.2 to escrow
        # That will set the market price to 1.2
        # Then bob will win Sam's sell. Bob's account will move 1.4 to escrow
        # That will set the market price to 1.4
        # Then Stuart's order will win Sid's order at 1.6.
        # Final Market price will be 1.6.

        self.stuart_inv = Inventory.objects.get(pk=self.stuart_inv.id)
        xactions = Transaction.objects.filter(buy_order=basil_buy)
        self.assertEquals(xactions.count(), 1)
        self.assertEquals(self.stuart_inv.status, Inventory.SOLD_STATUS)
        self.assertAlmostEquals(self.rishada.get_account_by_participant_id(self.basil.id).get_balance(), 13.33 - 1.2, places=7)

        self.sam_inv = Inventory.objects.get(pk=self.sam_inv.id)
        xactions = Transaction.objects.filter(buy_order=bob_buy)
        self.assertEquals(xactions.count(), 1)
        self.assertEquals(self.sam_inv.status, Inventory.SOLD_STATUS)
        self.assertAlmostEquals(self.rishada.get_account_by_participant_id(self.bob.id).get_balance(), 3.33 - 1.4, places=7)

        self.sid_inv = Inventory.objects.get(pk=self.sid_inv.id)
        xactions = Transaction.objects.filter(buy_order=barb_buy)
        self.assertEquals(xactions.count(), 1)
        self.assertEquals(self.sid_inv.status, Inventory.SOLD_STATUS)
        self.assertAlmostEquals(self.rishada.get_account_by_participant_id(self.barb.id).get_balance(), 7.33 - 1.6, places=7)

        # Check to make sure no money has entered or left the system
        cur_economy = LedgerEntry.objects.all().aggregate(Sum('amount'))['amount__sum']
        self.assertAlmostEquals(cur_economy, base_economy, places=7)

        # Test market
        self.assertEquals(market.current_market_price(self.stock_a), 1.6)
        self.assertIsNone(market.current_bid_price(self.stock_a))
        self.assertIsNone(market.current_ask_price(self.stock_a))

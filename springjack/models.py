from django.db import models
from market.models import Participant, Transaction
from random import random
from django.utils import timezone
import uuid
from django.db.models import Q, Count, Min, Sum, Avg

from rishada.rishada import RishadaBackend, InsufficientFundsError, AuthorizationError, RishadaAccount
import uuid

import sys

'''
For the moment, we are storing all of the account and transaction
details in the database. This is really just a proxy for Bitcoin, as
my current belief is that doing this in Blockchain will be better and
more secure.
'''


class Account(models.Model, RishadaAccount):
    id = models.AutoField(primary_key=True)
    owner = models.ForeignKey('market.Participant', null=False)
    #address = models.CharField(max_length=56, unique=True, null=False)
    account_key = models.CharField(max_length=56, default=uuid.uuid4, unique=True, null=False)

    '''
    Required by RishadaAccount

    Returns a unqiue string indentifier that this account can be
    addressed by.
    '''

    def get_account_id(self):
        return self.account_key

    '''
    Required by RishadaAccount

    Returns a floating point number, which is the current balance of
    the account/wallet.
    '''

    def get_balance(self):
        credits_dict = LedgerEntry.objects.filter(account=self).aggregate(Sum('amount'))
        debits_dict = LedgerEntry.objects.filter(other_account=self).aggregate(Sum('amount'))
        credit = 0.0
        if credits_dict is not None and 'amount__sum' in credits_dict and credits_dict['amount__sum'] is not None:
            credit = credits_dict['amount__sum']
        #debit = 0.0
        # if debits_dict is not None and 'amount__sum' in debits_dict and debits_dict['amount__sum'] is not None:
        #    debit = debits_dict['amount__sum']
        #balance = credit + debit
        #sys.stderr.write("SpringjackAccount[{}]: credit {}, debit {}\n".format(self.get_address(), str(credit), str(debit)))
        balance = credit
        sys.stderr.write("SpringjackAccount[{}]: balance {}\n".format(self.get_account_id(), str(balance)))
        return balance

    '''
    Required by RishadaAccount

    Performs the transaction of paying to_account_id the amount
    specified.
    '''

    def transfer_funds(self, to_account_id, amount):
        famount = float(amount)  # REVISIT - REAL error checking
        sys.stderr.write(
            'SpringjackAccount: lets move {} from {} to {}.\n'.format(
                str(famount), str(
                    self.get_account_id()), str(to_account_id)))
        if amount <= 0.0:
            raise 'SpringjackAccount error - you need an amount bigger than 0'

        # Double entry bookkeeping.
        sentry = LedgerEntry()
        sentry.account = self
        sentry.amount = -1.0 * famount
        sentry.txid = 'foo'
        sentry.other_account = Account.objects.get(account_key=to_account_id)
        if sentry.account is None:
            raise 'Invalid Address error, dude.'
        sentry.save()
        rentry = LedgerEntry()
        rentry.account = sentry.other_account
        rentry.other_account = sentry.account
        rentry.amount = famount
        rentry.txid = sentry.txid
        rentry.save()

    def save(self, *args, **kwargs):
        # if self.address is None or self.address == '':
        #    self.address = uuid.uuid4().hex
        return super(Account, self).save(*args, **kwargs)  # Call the "real" save() method.


class LedgerEntry(models.Model):
    id = models.AutoField(primary_key=True)
    account = models.ForeignKey('Account', null=False, related_name='account')
    other_account = models.ForeignKey('Account', null=True, related_name='other_account')
    entry_datetime = models.DateTimeField(default=timezone.now, auto_now=True, null=False)
    amount = models.FloatField(null=False)
    other_memo = models.CharField(max_length=100, null=False)  # if the money is going out of the system?
    txid = models.CharField(max_length=100, null=False)


class Springjack(RishadaBackend):

    '''
    Required by RishadaBackend

    Given a participant_id, create a RishadaAccount and return it.
    '''

    def create_account(self, participant_id):
        acct = Account()
        part = Participant.objects.get(pk=participant_id)
        acct.owner = part
        acct.save()
        return acct

    '''
    Required by RishadaBackend

    Given an account_id, return a RishadaAccount.
    '''

    def get_account(self, account_id):
        acct = Account.objects.filter(account_key=account_id).first()
        return acct

    '''
    Required by RishadaBackend

    Returns the address of the account - a string which is a unique
    identifier of an account.
    '''

    def create_escrow_account(self, market_transaction_id):
        sys.stderr.write('Springjack:create_escrow_account ' + str(market_transaction_id) + "\n")
        escrowofficer = Participant.objects.filter(name='HoodwinkEscrowOfficer').first()
        escrow = Account()
        escrow.owner = escrowofficer
        escrow.save()
        return escrow

    '''
    Required by RishadaBackend
    '''

    def get_account_by_participant_id(self, participant_id):
        acct = Account.objects.filter(owner=participant_id).first()
        return acct

    '''
    Required by RishadaBackend

    Returns the address of the account as identified by the
    market_transaction_id. The adress is a string which is a unique
    identifier of an account.
    '''

    def get_escrow_account_by_transaction_id(self, market_transaction_id):
        # Springjack just uses the same escrow account for all transactions.
        escrowofficer = Participant.objects.filter(name='HoodwinkEscrowOfficer').first()
        return self.get_account_by_participant_id(escrowofficer.id)

    '''
    related_transaction: the Market Transaction that we are transacting.
    '''

    def create_escrow_transaction(self, related_transaction):
        # check that the funder has funds
        buyer = related_transaction.buy_order.buyer
        buyer_acct = Account.objects.filter(owner=buyer).first()
        if buyer_account.balance() < related_transaction.price:
            # Insufficient Funds!
            raise InsufficientFundsError()

        # create a deposit escrow transaction
        seller = related_transaction.sell_order.seller
        seller_acct = Account.objects.filter(owner=seller).first()

        escrow = EscrowAccount()
        escrow.funding_account = buyer_acct
        escrow.receiving_account = seller_acct
        escrow.market_transaction = related_transaction
        escrow.save()

        # remove funds from the funders account and put them in escrow
        seller_acct.withdraw_funds(related_transaction.price, escrow, 'some memo', int(random() * 100000000000000))

        # done!

        pass

    def release_escrow_transaction(self, related_transaction):
        # find/verify that we have an esrow transaction for this

        # check that the funder has funds
        buyer = related_transaction.buy_order.buyer
        buyer_acct = Account.objects.filter(owner=buyer).first()
        if buyer_account.balance() < related_transaction.price:
            # Insufficient Funds!
            raise InsufficientFundsError()

        # create a deposit escrow transaction
        seller = related_transaction.sell_order.seller
        seller_acct = Account.objects.filter(owner=seller).first()

        escrow = EscrowAccount()
        escrow.funding_account = buyer_acct
        escrow.receiving_account = seller_acct
        escrow.market_transaction = related_transaction
        escrow.save()

        # remove funds from the funders account and put them in escrow
        seller_acct.withdraw_funds(related_transaction.price, escrow, 'some memo', int(random() * 100000000000000))

        # done!

        pass

        # create a withdrawl escrow transaction

        # add funds to recipient's account

        # done!

        pass

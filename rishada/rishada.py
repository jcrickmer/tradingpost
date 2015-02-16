import sys
from market.models import Transaction

'''
This is the abstracted payment gateway for the Marketplace to use. It
could be backed by Bitcoin, or by Springjack (the money proxy for
testing).

Rishada assumes that the underlieing backend has the tools, keys,
permissions, and authorities to perform all of the transactions. If
those permissions are missing or incorrect, the backend should raise
an AuthorizationError.

In the case of Bitcoin, I think that this means that the backend needs
to manage all of the private and public keys of each
wallet/address. For our Springjack proxy, there is no authorization.

'''


class Rishada:

    def __init__(self, backend):
        if not isinstance(backend, RishadaBackend):
            raise Error()
        self.backend = backend

    '''
    Create a new account. Return the RishadaAccount.
    '''

    def create_account(self, participant_id):
        return self.backend.create_account(participant_id)

    '''
    Given a participant_id, return a RishadaAccount.
    '''

    def get_account_by_participant_id(self, participant_id):
        return self.backend.get_account_by_participant_id(participant_id)

    '''
    Retrieve the current balace of an account. This should only fail
    if the account_id is unknown. No key or authorization should be
    required to check the balance.
    '''

    def get_balance(self, account_id):
        account = self.backend.get_account(account_id)
        return account.get_balance()

    '''
    Given an account address to send funds from, and an address to
    send those funds, transfer the amount. This could raise an
    InsufficientFundsError if the amount exceeds the balance of the
    account referenced by from_address, or a AuthorizationError if we
    don't have the authorization necessary on the funding account.
    '''

    def transfer_funds(self, from_address, to_address, amount):
        account = self.backend.get_account(from_address)
        account.transfer_funds(to_address, amount)
        return True

    '''
    Move funds from one account into a new escrow account. The
    market_transaction_id will be used as a key for the new
    account/wallet that is created in the backend.
    '''

    def escrow_funds(self, from_address, market_transaction_id, amount):
        if amount <= 0.0:
            raise Error()
        # Create a new account/wallet, with a new address.
        escrow = self.backend.create_escrow_account(market_transaction_id)

        # this could throw an InsufficientFundsError or an AuthorizationError
        self.transfer_funds(from_address, escrow.get_account_id(), amount)

        return True

    '''
    The buyer has confirmed receipt of the goods from seller, and thus
    releases his funds from escrow to the sellers account.

    The backend is responsible for being able to identify the escrow
    address and the seller address from the market_transaction_id. The
    entire balance of the escrow address will be transfered to the
    seller.
    '''

    def release_escrow(self, seller_account_id, market_transaction_id):
        # REVISIT - this needs to be fixed. the backend is not the place to figure
        # out the escrow address by transaction. That needs to be in the market, I
        # think.
        escrow_account = self.backend.get_escrow_account_by_transaction_id(market_transaction_id)
        seller_account = self.backend.get_account(seller_account_id)
        xaction = Transaction.objects.get(pk=market_transaction_id)
        sys.stderr.write(
            "Rishada: release id {} to seller {} from escrow {} for {}\n".format(
                str(market_transaction_id),
                str(seller_account),
                str(escrow_account),
                xaction.price))

        # this could throw an AuthorizationError, which would be a deep problem indeed.
        self.transfer_funds(escrow_account.get_account_id(), seller_account.get_account_id(), xaction.price)

        return True


class RishadaBackend:

    '''
    Given an account_id, return a RishadaAccount.
    '''

    def get_account(self, account_id):
        raise 'AbstractClassError - RishadaAccount.get_account'

    '''
    Given an account_id, return a RishadaAccount.
    '''

    def get_account_by_participant_id(self, participant_id):
        raise 'AbstractClassError - RishadaAccount.get_account_by_participant_id'

    '''
    Create a new account for the given foreign key participant_id.
    '''

    def create_account(self, participant_id):
        raise 'AbstractClassError - RishadaAccount.create_account'

    '''
    Returns the address of the account - a string which is a unique
    identifier of an account.
    '''

    def create_escrow_account(self, market_transaction_id):
        pass

    '''
    Returns the address of the account as identified by the
    market_transaction_id. The adress is a string which is a unique
    identifier of an account.
    '''

    def get_escrow_account_by_transaction_id(self, market_transaction_id):
        raise 'AbstractClassError - RishadaAccount.get_account_id'


class RishadaAccount:

    '''
    Returns a unqiue string indentifier that this account can be
    addressed by.
    '''

    def get_account_id(self):
        raise 'AbstractClassError - RishadaAccount.get_account_id'

    '''
    Returns a floating point number, which is the current balance of
    the account/wallet.
    '''

    def get_balance(self):
        raise 'AbstractClassError - RishadaAccount.get_balance'

    '''
    Performs the transaction of paying to_account_id the amount
    specified.
    '''

    def transfer_funds(self, to_account_id, amount):
        raise 'AbstractClassError - RishadaAccount.transfer_funds'


class AuthorizationError:
    pass


class InsufficientFundsError:
    pass

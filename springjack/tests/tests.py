from django.test import TestCase


class UseCasesTestCases(TestCase):

    def test_deposit_funds(self):
        self.assertEquals(False)

    def test_transfer_funds_to_escrow(self):
        self.assertEquals(False)

    def test_release_funds_from_escrow(self):
        self.assertEquals(False)

    def test_refund_escrow(self):
        self.assertEquals(False)

    def test_withdrwaw_funds(self):
        self.assertEquals(False)

    def test_get_acct_balance(self):
        self.assertEquals(False)

    def test_get_acct_transaction_history(self):
        self.assertEquals(False)

    def test_get_escrow_balance(self):
        self.assertEquals(False)

    def test_get_escrow_transaction_history(self):
        self.assertEquals(False)

# tradingpost
Trading Post

Market
 Stock
 Participant
  Inventory
  Broker Account
 Order
 Transaction

Brokerage
 Account
  Ledger Entry (a credit or debit)
   has an amount
   references another account where the money is going or came from



As a Participant (Buyer), I want to make a Buy Order for a Stock on the Market.
As a Participant (Seller), I want to make a Sell Order for Inventory that I own on the Market.
As the Market, I want to connect the Buy Order and the Sell Order in a transaction.
As the Market, on behalf of the Buyer, I want to put funds into Escrow for the transaction.
As a Participant (Seller), I want to ship my Inventory to the Buyer for this transaction.
As a Participant (Buyer), I want to confirm delivery of Inventory from the Seller.
As the Broker, on behalf of the Buyer, I want to release the Escrow funds to the Seller.


Market
 has stock
 has participants

Stock
 belongs to the market

Participant
 belongs to a market
 has inventory (as an owner)
 places Orders on the Market
 has a Broker Account (#)

Inventory
 is made of Stock.
 has an owner

Order
 has a type
 has a price
 has an owner
 specfies stock (possibly through Inventory)
 has a status

Transaction
 has a Buy Order
 has a Sell Order
 has a value
 has a status
  <start> initiated
  funded by buyer
  inventory shipped
  inventory received/confirmed
  seller is paid <closed>


Brokerage
Account
 is identifiable
 has an owner
 has a balance (derived from Ledge Entries)
 has Ledger Entries

Ledger Entry (a credit or debit)
 belongs to an account
 has an amount
 has a time stamp
 references another account where the money is going or came from
 has a basis in some external system (Bitcoin network, bank account, etc...)


Bitcoin model...
 Wallet
  owner (identified by private key)
  address(es??)
  transactions
   address
    in

# This smart contract has been writen to provide a simple way to mint editions of on-chain artwork with the Tezos blockchain
# It is written in the Legacy SmartPy programming language speicifally for use with the legacy.smartpy.io/ide compiler
# This contract is a combination of the oroginal Zero Contract (for 1/1) mixed with the SmartPy FA2 Template
# Author: jestemzero with assistance from ChatGPT, Gemini and Claude LLMs
# xTwiiter: @jestemzero
# Warpcast: @jestemzero
# Discord: @jestemzero

# IMPORTANT: On-chain artwork is saved with a datarUri format in the "artifactUri" metadata attribute
# Objkt.com currently does not recognize artifactUri strings longer than 254 characters
# Any token exceeding this limitation needs to contact Objkt.com directly and request the limitation be removed for their collection

import smartpy as sp

# Define contract metadata
# Format the "content" key's value as a JSON string
# Ensure to include the minimum keys but additional keys can be added without detriment
# name, description, interfaces, symbol, creators, type, imageUri
# imageUri is limited to 254 characters to display on Objkt.com unless limitation is lifted by the marketplace
contract_metadata = sp.big_map(
    {
        "": sp.utils.bytes_of_string('tezos-storage:content'),
        "content": sp.utils.bytes_of_string(
            '{"name": "Project Name","description": "Project Description","interfaces": ["TZIP-012", "TZIP-016"],"authors": ["Author Name"],"authoraddress": ["Valid tz... address"],"symbol": "SYMBOL","creators": ["Valid tz... address"],"type":"art","imageUri":"URI string"}'
        )
    }
)

# Use this value to ensure compilers set the proper administrator address control
ADMIN_ADDRESS = sp.address("tz1ADDRESS")

class Error_message:
    def token_undefined(self):       return "FA2_TOKEN_UNDEFINED"
    def insufficient_balance(self):  return "FA2_INSUFFICIENT_BALANCE"
    def not_operator(self):          return "FA2_NOT_OPERATOR"
    def not_owner(self):             return "FA2_NOT_OWNER"
    def operators_unsupported(self): return "FA2_OPERATORS_UNSUPPORTED"
    def not_admin(self):             return "FA2_NOT_ADMIN"
    def not_admin_or_operator(self): return "FA2_NOT_ADMIN_OR_OPERATOR"
    def paused(self):                return "FA2_PAUSED"

class Batch_transfer:
    def get_transfer_type(self):
        tx_type = sp.TRecord(
            to_ = sp.TAddress,
            token_id = sp.TNAT,
            amount = sp.TNat
        ).layout(("to_", ("token_id", "amount")))
        
        transfer_type = sp.TRecord(
            from_ = sp.TAddress,
            txs = sp.TList(tx_type)
        ).layout(("from_", "txs"))
        
        return transfer_type

    def get_type(self):
        return sp.TList(self.get_transfer_type())

    def item(self, from_, txs):
        v = sp.record(from_ = from_, txs = txs)
        return sp.set_type_expr(v, self.get_transfer_type())

class Operator_param:
    def get_type(self):
        return sp.TRecord(
            owner = sp.TAddress,
            operator = sp.TAddress,
            token_id = sp.TNAT
        ).layout(("owner", ("operator", "token_id")))

    def make(self, owner, operator, token_id):
        r = sp.record(
            owner = owner,
            operator = operator,
            token_id = token_id
        )
        return sp.set_type_expr(r, self.get_type())

class Ledger_key:
    def make(self, user, token):
        user = sp.set_type_expr(user, sp.TAddress)
        token = sp.set_type_expr(token, sp.TNAT)
        result = sp.pair(user, token)
        return result

class Ledger_value:
    def get_type():
        return sp.TRecord(balance = sp.TNat)
        
    def make(balance):
        return sp.record(balance = balance)

class Operator_set:
    def inner_type(self):
        return sp.TRecord(
            owner = sp.TAddress,
            operator = sp.TAddress,
            token_id = sp.TNAT
        ).layout(("owner", ("operator", "token_id")))

    def key_type(self):
        return self.inner_type()

    def make(self):
        return sp.big_map(tkey = self.key_type(), tvalue = sp.TUnit)

    def make_key(self, owner, operator, token_id):
        metakey = sp.record(
            owner = owner,
            operator = operator,
            token_id = token_id
        )
        return sp.set_type_expr(metakey, self.inner_type())

    def add(self, set, owner, operator, token_id):
        set[self.make_key(owner, operator, token_id)] = sp.unit

    def remove(self, set, owner, operator, token_id):
        del set[self.make_key(owner, operator, token_id)]

    def is_member(self, set, owner, operator, token_id):
        return set.contains(self.make_key(owner, operator, token_id))

class Balance_of:
    def request_type():
        return sp.TRecord(
            owner = sp.TAddress,
            token_id = sp.TNAT
        ).layout(("owner", "token_id"))

    def response_type():
        return sp.TList(
            sp.TRecord(
                request = Balance_of.request_type(),
                balance = sp.TNat
            ).layout(("request", "balance")))

    def entrypoint_type():
        return sp.TRecord(
            callback = sp.TContract(Balance_of.response_type()),
            requests = sp.TList(Balance_of.request_type())
        ).layout(("requests", "callback"))

class Token_meta_data:
    def get_type(self):
        return sp.TRecord(
            token_id = sp.TNat,
            token_info = sp.TMap(sp.TString, sp.TBytes)
        )

    def set_type_and_layout(self, expr):
        sp.set_type(expr, self.get_type())

class Token_id_set:
    def empty(self):
        return sp.nat(0)

    def add(self, totalTokens, tokenID):
        sp.verify(totalTokens == tokenID, message = "Token-IDs should be consecutive")
        totalTokens.set(tokenID + 1)

    def contains(self, totalTokens, tokenID):
        return (tokenID < totalTokens)

    def cardinal(self, totalTokens):
        return totalTokens

def mutez_transfer(contract, params):
    sp.verify(sp.sender == contract.data.administrator)
    sp.set_type(params.destination, sp.TAddress)
    sp.set_type(params.amount, sp.TMutez)
    sp.send(params.destination, params.amount)
    
class FA2_core(sp.Contract):
    def __init__(self, metadata):
        self.error_message = Error_message()
        self.operator_set = Operator_set()
        self.init(
            ledger = sp.big_map(tvalue = Ledger_value.get_type()),
            admin = ADMIN_ADDRESS,
            token_metadata = sp.big_map(tkey = sp.TNat, tvalue = Token_meta_data().get_type()),
            operators = self.operator_set.make(),
            all_tokens = sp.nat(0),
            next_token_id=sp.nat(0),
            metadata = metadata,
            paused = False,
            total_supply = sp.big_map(tkey = sp.TNat, tvalue = sp.TNat),
            children = sp.set(t=sp.TAddress),
            parents = sp.set(t=sp.TAddress)
        )

    @sp.entrypoint
    def transfer(self, params):
        sp.verify(~self.data.paused, message = self.error_message.paused())
        sp.set_type(params, Batch_transfer().get_type())
        
        sp.for transfer in params:
            sp.for tx in transfer.txs:
                sender_verify = ((transfer.from_ == sp.sender) |
                               (sp.sender == self.data.admin) |
                               (self.operator_set.is_member(self.data.operators,
                                                          transfer.from_,
                                                          sp.sender,
                                                          tx.token_id)))
                                                          
                sp.verify(sender_verify, message = self.error_message.not_operator())
                sp.verify(
                    self.data.token_metadata.contains(tx.token_id),
                    message = self.error_message.token_undefined()
                )
                
                sp.if (tx.amount > 0):
                    from_user = sp.pair(transfer.from_, tx.token_id)
                    sp.verify(
                        (self.data.ledger[from_user].balance >= tx.amount),
                        message = self.error_message.insufficient_balance())
                    
                    to_user = sp.pair(tx.to_, tx.token_id)
                    self.data.ledger[from_user].balance = sp.as_nat(
                        self.data.ledger[from_user].balance - tx.amount)
                    
                    sp.if self.data.ledger.contains(to_user):
                        self.data.ledger[to_user].balance += tx.amount
                    sp.else:
                        self.data.ledger[to_user] = Ledger_value.make(tx.amount)
        
    # Mint Interaction
    # The entrypoint does nothing more than send the mint action to the address provided
    # All metadata attributes are input into the contract interaction (for example on the Better Call Dev interface)
    # When minting "name", "artifactUri" and "creators" attributes must be present for a valid token connected to an artists profile
    # A longer list of attributes is highly recommended tailored to each collection's needs
    @sp.entrypoint
    def mint(self, params):
        # Check if the sender is the admin
        sp.verify(sp.sender == self.data.admin, message = "Not authorized")
        
        # Automatically compute the next token_id using the next_token_id counter
        token_id = self.data.next_token_id
        
        # Store token metadata (if any)
        self.data.token_metadata[token_id] = sp.record(
            token_id = token_id,
            token_info = params.metadata
        )
        
        # Update the ledger: (address, token_id) -> balance
        self.data.ledger[(params.to_, token_id)] = sp.record(balance=params.amount)
        
        # Update total supply for this token_id
        sp.if ~self.data.total_supply.contains(token_id):
            self.data.total_supply[token_id] = 0
        self.data.total_supply[token_id] += params.amount
        
        # Increment the next_token_id counter for future mints
        self.data.next_token_id += 1

    @sp.entrypoint
    def balance_of(self, params):
        sp.verify(~self.data.paused, message = self.error_message.paused())
        sp.set_type(params, Balance_of.entrypoint_type())
        
        def process_request(req):
            user = sp.pair(req.owner, req.token_id)
            sp.verify(self.data.token_metadata.contains(req.token_id), 
                     message = self.error_message.token_undefined())
            
            sp.if self.data.ledger.contains(user):
                balance = self.data.ledger[user].balance
            sp.else:
                balance = sp.nat(0)
                
            sp.result(
                sp.record(
                    request = sp.record(
                        owner = sp.set_type_expr(req.owner, sp.TAddress),
                        token_id = sp.set_type_expr(req.token_id, sp.TNat)),
                    balance = balance))
                    
        res = sp.local("responses", params.requests.map(process_request))
        destination = sp.set_type_expr(params.callback, 
                                     sp.TContract(Balance_of.response_type()))
        sp.transfer(res.value, sp.mutez(0), destination)

    @sp.entrypoint
    def update_operators(self, params):
        sp.for update in params:
            with update.match_cases() as arg:
                with arg.match("add_operator") as upd:
                    sp.verify((upd.owner == sp.sender) | (sp.sender == self.data.admin),
                             message = self.error_message.not_admin_or_operator())
                    self.operator_set.add(self.data.operators,
                                        upd.owner,
                                        upd.operator,
                                        upd.token_id)
                with arg.match("remove_operator") as upd:
                    sp.verify((upd.owner == sp.sender) | (sp.sender == self.data.admin),
                             message = self.error_message.not_admin_or_operator())
                    self.operator_set.remove(self.data.operators,
                                           upd.owner,
                                           upd.operator,
                                           upd.token_id)

    # The burn token interaction can only be executed by the token owner
    # Objkt.com has a built-in burn mechanisam that can be used as well
    # This is provided for an alternative means or for tokens no present on the Objkt marketplace
    @sp.entrypoint
    def burn(self, params):
        sp.set_type(params, sp.TRecord(token_id = sp.TNat, amount = sp.TNat))
        sp.verify(params.token_id < self.data.next_token_id, self.error_message.token_undefined())
        user = sp.pair(sp.sender, params.token_id)
    
        # Check if the sender owns the token
        sp.verify(self.data.ledger.contains(user), self.error_message.not_owner())
        sp.verify(self.data.ledger[user].balance >= params.amount, self.error_message.insufficient_balance())
    
        self.data.ledger[user].balance = sp.as_nat(self.data.ledger[user].balance - params.amount)
        
        sp.if self.data.total_supply[params.token_id] >= params.amount:
            self.data.total_supply[params.token_id] = sp.as_nat(self.data.total_supply[params.token_id] - params.amount)
    
        sp.if self.data.ledger[user].balance == 0:
            self.data.ledger[user].balance = 0
            self.data.total_supply[params.token_id] = 0
    
            # Optionally, delete the token metadata only if needed (this depends on your requirements)
            sp.if self.data.token_metadata.contains(params.token_id):
                del self.data.token_metadata[params.token_id]
                
    @sp.entrypoint
    def add_child(self, address):
        sp.set_type(address, sp.TAddress)
        sp.verify(sp.sender == self.data.admin, "Only the contract owner can add children")
        self.data.children.add(address)
    
    @sp.entrypoint
    def remove_child(self, address):
        sp.set_type(address, sp.TAddress)
        sp.verify(sp.sender == self.data.admin, "Only the contract owner can remove children")
        self.data.children.remove(address)
    
    @sp.entrypoint
    def add_parent(self, address):
        sp.set_type(address, sp.TAddress)
        sp.verify(sp.sender == self.data.admin, "Only the contract owner can add parents")
        self.data.parents.add(address)
    
    @sp.entrypoint
    def remove_parent(self, address):
        sp.set_type(address, sp.TAddress)
        sp.verify(sp.sender == self.data.admin, "Only the contract owner can remove parents")
        self.data.parents.remove(address)
        
    @sp.entrypoint
    def set_pause(self, params):
        sp.verify(sp.sender == self.data.admin, message = self.error_message.not_admin())
        self.data.paused = params

    @sp.offchain_view(pure = True)
    def get_balance(self, req):
        sp.set_type(req, sp.TRecord(
            owner = sp.TAddress,
            token_id = sp.TNat
        ).layout(("owner", "token_id")))
        
        user = sp.pair(req.owner, req.token_id)
        sp.verify(self.data.token_metadata.contains(req.token_id), 
                 message = self.error_message.token_undefined())
        sp.result(self.data.ledger[user].balance)

    @sp.offchain_view(pure = True)
    def count_tokens(self):
        sp.result(self.data.all_tokens)

    @sp.offchain_view(pure = True)
    def does_token_exist(self, tok):
        sp.set_type(tok, sp.TNat)
        sp.result(self.data.token_metadata.contains(tok))

    @sp.offchain_view(pure = True)
    def all_tokens(self):
        sp.result(sp.range(0, self.data.all_tokens))

    @sp.offchain_view(pure = True)
    def total_supply(self, tok):
        sp.result(self.data.total_supply[tok])

    @sp.offchain_view(pure = True)
    def is_operator(self, query):
        sp.set_type(query,
                   sp.TRecord(token_id = sp.TNat,
                            owner = sp.TAddress,
                            operator = sp.TAddress).layout(
                                ("owner", ("operator", "token_id"))))
        sp.result(
            self.operator_set.is_member(self.data.operators,
                                      query.owner,
                                      query.operator,
                                      query.token_id)
        )

    @sp.offchain_view(pure=True)
    def get_children(self):
        sp.result(self.data.children)
    
    @sp.offchain_view(pure=True)
    def get_parents(self):
        sp.result(self.data.parents)
        
class View_consumer(sp.Contract):
    """Helper contract for testing view methods"""
    def __init__(self, contract):
        self.contract = contract
        self.init(
            last_sum = 0,
            operator_support = True  # Always True for NFT editions
        )

    @sp.entrypoint
    def reinit(self):
        self.data.last_sum = 0

    @sp.entrypoint
    def receive_balances(self, params):
        sp.set_type(params, Balance_of.response_type())
        self.data.last_sum = 0
        sp.for resp in params:
            self.data.last_sum += resp.balance

def add_test(is_default=True):
    @sp.add_test(name="NFT Editions Test Scenarios", is_default=is_default)
    def test():
        scenario = sp.test_scenario()

        # Test accounts
        admin = ADMIN_ADDRESS
        artist = sp.test_account("Artist")
        collector1 = sp.test_account("Collector1")
        collector2 = sp.test_account("Collector2")

        scenario.h2("Accounts")
        scenario.show([artist, collector1, collector2])
        
        # Contract deployment
        c1 = FA2_core(metadata=contract_metadata)
        scenario += c1

        # Test minting 3 tokens
        scenario.h3("Mint 3 Tokens")
        
        # Mint 10 copies of edition #1 (token_id 0) to artist
        edition1_md = sp.map(l={
            "": sp.utils.bytes_of_string("ipfs://QmZ1"),
            "name": sp.utils.bytes_of_string("Edition #1"),
            "symbol": sp.utils.bytes_of_string("ED1"),
            "decimals": sp.utils.bytes_of_string("0")
        })
        c1.mint(to_=artist.address, amount=10, metadata=edition1_md).run(sender=admin)

        # Mint 5 copies of edition #2 (token_id 1) to artist
        edition2_md = sp.map(l={
            "": sp.utils.bytes_of_string("ipfs://QmZ2"),
            "name": sp.utils.bytes_of_string("Edition #2"),
            "symbol": sp.utils.bytes_of_string("ED2"),
            "decimals": sp.utils.bytes_of_string("0")
        })
        c1.mint(to_=artist.address, amount=5, metadata=edition2_md).run(sender=admin)

        # Mint 3 copies of a new burn token (token_id 2)
        burn_token_md = sp.map(l={
            "": sp.utils.bytes_of_string("ipfs://QmZ3"),
            "name": sp.utils.bytes_of_string("Burned Edition"),
            "symbol": sp.utils.bytes_of_string("BURN"),
            "decimals": sp.utils.bytes_of_string("0")
        })
        c1.mint(to_=artist.address, amount=3, metadata=burn_token_md).run(sender=admin)

        # Verify minting state for all tokens
        scenario.verify(c1.data.ledger[sp.pair(artist.address, 0)].balance == 10)  # Edition #1
        scenario.verify(c1.data.ledger[sp.pair(artist.address, 1)].balance == 5)   # Edition #2
        scenario.verify(c1.data.ledger[sp.pair(artist.address, 2)].balance == 3)   # Burn Token

        scenario.verify(c1.data.total_supply[0] == 10)  # Total supply for token_id 0
        scenario.verify(c1.data.total_supply[1] == 5)   # Total supply for token_id 1
        scenario.verify(c1.data.total_supply[2] == 3)   # Total supply for burn token

        scenario.h3("Transfer Tests")
        
        # Test basic transfer using batch_transfer instance for token_id 0 and token_id 1
        batch_transfer = Batch_transfer()
        c1.transfer(
            [
                batch_transfer.item(
                    from_=artist.address,
                    txs=[
                        sp.record(to_=collector1.address, amount=3, token_id=0),  # Edition #1
                        sp.record(to_=collector2.address, amount=2, token_id=1)   # Edition #2
                    ]
                )
            ]
        ).run(sender=artist)

        # Verify balances after transfer
        scenario.verify(c1.data.ledger[sp.pair(artist.address, 0)].balance == 7)   # Edition #1
        scenario.verify(c1.data.ledger[sp.pair(collector1.address, 0)].balance == 3)  # Edition #1
        scenario.verify(c1.data.ledger[sp.pair(artist.address, 1)].balance == 3)   # Edition #2
        scenario.verify(c1.data.ledger[sp.pair(collector2.address, 1)].balance == 2)  # Edition #2

        # Test transferring more editions than one owns (should fail)
        scenario.h3("Transfer more editions than owned (Fail)")
        c1.transfer(
            [
                batch_transfer.item(
                    from_=artist.address,
                    txs=[sp.record(to_=collector2.address, amount=8, token_id=0)]  # Artist only has 7 left
                )
            ]
        ).run(sender=artist, valid=False)  # This should fail because the artist doesn't own 8 editions
        
        scenario.h3("Burn Token Tests")

        # Now, we only burn tokens of token_id 2 (the burn token)
        # Artist wants to burn 3 burn tokens
        c1.burn(token_id=2, amount=3).run(sender=artist)

        # Verify burn results
        scenario.verify(c1.data.ledger[sp.pair(artist.address, 2)].balance == 0)  # Burn tokens removed
        scenario.verify(c1.data.total_supply[2] == 0)   # Total supply for burn token is now 0

        scenario.h3("Multi-Edition Tests")
        
        # Mint a third edition (token_id 3)
        edition3_md = sp.map(l={
            "": sp.utils.bytes_of_string("ipfs://QmZ3"),
            "name": sp.utils.bytes_of_string("Edition #3"),
            "symbol": sp.utils.bytes_of_string("ED3"),
            "decimals": sp.utils.bytes_of_string("0")
        })
        
        c1.mint(to_=artist.address, amount=5, metadata=edition3_md).run(sender=admin)

        # Test multi-token transfer
        c1.transfer(
            [
                batch_transfer.item(
                    from_=artist.address,
                    txs=[
                        sp.record(to_=collector2.address, amount=2, token_id=3)  # New Edition #3
                    ]
                )
            ]
        ).run(sender=artist)

        scenario.h3("Operator Tests")
        operator = sp.test_account("Operator")
        
        # Add operator
        c1.update_operators([sp.variant("add_operator", Operator_param().make(owner=artist.address, operator=operator.address, token_id=3))]).run(sender=artist)

        # Test operator transfer
        c1.transfer(
            [
                batch_transfer.item(
                    from_=artist.address,
                    txs=[sp.record(to_=collector1.address, amount=1, token_id=3)]
                )
            ]
        ).run(sender=operator)

        # Test unauthorized operator
        c1.transfer(
            [
                batch_transfer.item(
                    from_=artist.address,
                    txs=[sp.record(to_=collector1.address, amount=1, token_id=1)]
                )
            ]
        ).run(sender=operator, valid=False)

        scenario.h3("View Tests")
        consumer = View_consumer(c1)
        scenario += consumer

        # Test balance_of view
        c1.balance_of(
            sp.record(
                requests=[
                    sp.record(owner=artist.address, token_id=0),
                    sp.record(owner=collector1.address, token_id=0),
                    sp.record(owner=collector2.address, token_id=0)
                ],
                callback=sp.contract(
                    Balance_of.response_type(),
                    consumer.address,
                    entry_point="receive_balances"
                ).open_some()
            )
        ).run(sender=collector1)

        # Test total supply view
        scenario.verify(c1.data.total_supply[0] == 10)  # Edition #1 total supply
        scenario.verify(c1.data.total_supply[1] == 5)   # Edition #2 total supply
        scenario.verify(c1.data.total_supply[2] == 0)   # Burn token total supply (should be 0)

        # Test Child and Parent Control (Address Lists)
        scenario.h3("Test Child and Parent Address Management")

        # Test adding addresses
        test_address = sp.address("tz1XXExampleAddress")
        scenario.h3("Adding a child address")
        scenario += c1.add_child(test_address).run(sender=ADMIN_ADDRESS)
        scenario.verify(c1.data.children.contains(test_address))

        # Test removing addresses
        scenario.h3("Removing a child address")
        scenario += c1.remove_child(test_address).run(sender=ADMIN_ADDRESS)
        scenario.verify(~c1.data.children.contains(test_address))

# Add test to the compilation target
if "templates" not in __name__:
    add_test()
    sp.add_compilation_target(
        "nft_editions",
        FA2_core(
            metadata=contract_metadata
        )
    )

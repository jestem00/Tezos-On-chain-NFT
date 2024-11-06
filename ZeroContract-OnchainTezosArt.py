# This smart contract has been writen to provide a simple way to mint on-chain artwork with the Tezos blockchain
# It is written in the Legacy SmartPy programming language speicifally for use with the legacy.smartpy.io/ide compiler
# Author: jestemzero with assistance from ChatGPT, Gemini and Claude LLMs
# xTwiiter: @jestemzero
# Warpcast: @jestemzero
# Discord: @jestemzero

# IMPORTANT: On-chain artwork is saved with a datarUri format in the "artifactUri" metadata attribute
# Objkt.com currently does not recognize artifactUri strings longer than 254 characters
# Any token exceeding this limitation needs to contact Objkt.com directly and request the limitation be removed for their collection

import smartpy as sp

# Define the type for balance_of arguments
t_balance_of_args = sp.TRecord(
    requests=sp.TList(sp.TRecord(owner=sp.TAddress, token_id=sp.TNat)),
    callback=sp.TContract(
        sp.TList(
            sp.TRecord(
                request=sp.TRecord(owner=sp.TAddress, token_id=sp.TNat), balance=sp.TNat
            ).layout(("request", "balance"))
        )
    ),
).layout(("requests", "callback"))

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

# Definition for NFTs with both Ledger and FA2 compliance
class Fa2NftMint(sp.Contract):
    def __init__(self, metadata_base,ADMIN_ADDRESS):
        self.init_metadata("metadata_base", metadata_base)
        
        self.init(
            ledger=sp.big_map(tkey=sp.TNat, tvalue=sp.TAddress),
            admin=ADMIN_ADDRESS,
            next_token_id=sp.nat(0),
            operators=sp.big_map(
                tkey=sp.TRecord(
                    owner=sp.TAddress,
                    operator=sp.TAddress,
                    token_id=sp.TNat,
                ).layout(("owner", ("operator", "token_id"))),
                tvalue=sp.TUnit,
            ),
            metadata=metadata_base,
            token_metadata=sp.big_map(
                tkey=sp.TNat,
                tvalue=sp.TRecord(
                    token_id=sp.TNat,
                    token_info=sp.TMap(sp.TString, sp.TBytes),
                ),
            ),
            # New storage for the CHILD control
            # This currently a custom addition and not part of Tezos Standard, but does not break contracts
            # Can be removed if desired but must also remove the associated entrypoints, offchain views, and test scenario
            children = sp.set(t=sp.TAddress),
            parents = sp.set(t=sp.TAddress)
        )

    def only_owner(self, token_id):
        sp.verify(sp.sender == self.data.ledger[token_id], "You are not the Owner of this Token")
 

    # NEW ENTRYPOINTS FOR PARENT / CHILD FUNCTIONS
    # Remove these if not using #
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
    # END OF NEW ENTRYPOINTS
    
    @sp.entrypoint
    def transfer(self, batch):
        with sp.for_("transfer", batch) as transfer:
            with sp.for_("tx", transfer.txs) as tx:
                sp.set_type(
                    tx,
                    sp.TRecord(
                        to_=sp.TAddress, token_id=sp.TNat, amount=sp.TNat
                    ).layout(("to_", ("token_id", "amount"))),
                )
                sp.verify(tx.token_id < self.data.next_token_id, "This Token is Undefined for Transfer")
                sp.verify(
                    (transfer.from_ == sp.sender)
                    | self.data.operators.contains(
                        sp.record(
                            owner=transfer.from_,
                            operator=sp.sender,
                            token_id=tx.token_id,
                        )
                    ),
                    "You are not the Owner or Operator of this Token",
                )
                with sp.if_(tx.amount > 0):
                    sp.verify(
                        (tx.amount == 1)
                        & (self.data.ledger[tx.token_id] == transfer.from_),
                        "You cannot Transfer more Tokens than you Own",
                    )
                    self.data.ledger[tx.token_id] = tx.to_

    # This allows marketplaces to sell or transfer the token
    @sp.entrypoint
    def update_operators(self, actions):
        with sp.for_("update", actions) as action:
            with action.match_cases() as arg:
                with arg.match("add_operator") as operator:
                    self.only_owner(operator.token_id)
                    self.data.operators[operator] = sp.unit
                with arg.match("remove_operator") as operator:
                    self.only_owner(operator.token_id)
                    del self.data.operators[operator]

    @sp.entrypoint
    def balance_of(self, args):
        def f_process_request(req):
            sp.verify(req.token_id < self.data.next_token_id, "This Token has Undefined Balance")
            sp.result(
                sp.record(
                    request=sp.record(owner=req.owner, token_id=req.token_id),
                    balance=sp.eif(
                        self.data.ledger[req.token_id] == req.owner, sp.nat(1), 0
                    ),
                )
            )

        sp.set_type(args, t_balance_of_args)
        sp.transfer(args.requests.map(f_process_request), sp.mutez(0), args.callback)

    # Mint Interaction
    # The entrypoint does nothing more than send the mint action to the address provided
    # All metadata attributes are input into the contract interaction (for example on the Better Call Dev interface)
    # When minting "name", "artifactUri" and "creators" attributes must be present for a valid token connected to an artists profile
    # A longer list of attributes is highly recommended tailored to each collection's needs
    @sp.entrypoint
    def mint(self, params):
        sp.verify(sp.sender == ADMIN_ADDRESS, "Only the Collector Owner can Mint Tokens")
        token_id = sp.compute(self.data.next_token_id)
        self.data.token_metadata[token_id] = sp.record(
            token_id=token_id, token_info=params.metadata
        )
        self.data.ledger[token_id] = params.to_
        self.data.next_token_id += 1

    # The burn token interaction can only be executed by the token owner
    # Objkt.com has a built-in burn mechanisam that can be used as well
    # This is provided for an alternative means or for tokens no present on the Objkt marketplace
    @sp.entrypoint
    def burn(self, params):
        sp.set_type(params, sp.TRecord(token_id = sp.TNat))
        sp.verify(params.token_id < self.data.next_token_id, "Non-existand Token cannot be Burnt")
        sp.verify(self.data.ledger[params.token_id] == sp.sender, "You are not the Owner and cannot Burn this Token")
        del self.data.ledger[params.token_id]
        del self.data.token_metadata[params.token_id]

    @sp.offchain_view(pure=True)
    def get_administrator(self):
        sp.result(ADMIN_ADDRESS)
    
    @sp.offchain_view(pure=True)
    def all_tokens(self):
        sp.result(sp.range(0, self.data.next_token_id))

    @sp.offchain_view(pure=True)
    def get_balance(self, params):
        sp.set_type(
            params,
            sp.TRecord(owner=sp.TAddress, token_id=sp.TNat).layout(
                ("owner", "token_id")
            ),
        )
        sp.verify(params.token_id < self.data.next_token_id, "This Token has Undefined Offchain Balance")
        sp.result(sp.eif(self.data.ledger[params.token_id] == params.owner, 1, 0))

    @sp.offchain_view(pure=True)
    def total_supply(self, params):
        sp.verify(params.token_id < self.data.next_token_id, "This Collection has Undefined Balance")
        sp.result(1)

    @sp.offchain_view(pure=True)
    def is_operator(self, params):
        sp.result(self.data.operators.contains(params))

    # ADDITIOANL VIEWS FOR PARENT/CHILD
    # Remove these if not using #
    @sp.offchain_view(pure=True)
    def get_children(self):
        sp.result(self.data.children)
    
    @sp.offchain_view(pure=True)
    def get_parents(self):
        sp.result(self.data.parents)
    # END OF ADDITIONAL VIEWS
    
# Function to create metadata for test scenario
def make_metadata(token_data):
    core_metadata = {
        "name": sp.bytes("0x" + token_data["name"].encode("utf-8").hex()),
        "description": sp.bytes("0x" + token_data["description"].encode("utf-8").hex()),
        "artifactUri": sp.bytes("0x" + token_data["artifactUri"].encode("utf-8").hex()),
    }
    return core_metadata

# Testing Scenarios
if "templates" not in __name__:
    alice = sp.test_account("Alice")
    bob = sp.test_account("Bob")
    tok0_md = make_metadata({
        "name": "Token Name",
        "description": "Token Description",
        "artifactUri": "data:image/svg+xml;base64",
    })

    @sp.add_test(name="Test")
    def test():
        scenario = sp.test_scenario()
        c1 = Fa2NftMint(metadata_base=contract_metadata,ADMIN_ADDRESS=ADMIN_ADDRESS)
        scenario += c1
  
        # Mint tok0 with its metadata (should succeed with admin)
        scenario += c1.mint(sp.record(to_=ADMIN_ADDRESS, metadata=tok0_md)).run(sender=ADMIN_ADDRESS)

        # Add Bob as an operator for token_id 0 (should succeed with Alice)
        scenario += c1.update_operators([
            sp.variant("add_operator", sp.record(owner=ADMIN_ADDRESS, operator=bob.address, token_id=sp.nat(0)))
        ]).run(sender=ADMIN_ADDRESS)

        # Check balance of administrator for tok0 (should be 1)
        scenario.verify(c1.get_balance(sp.record(owner=ADMIN_ADDRESS, token_id=0)) == 1)

        # Verify description field in the metadata
        expected_description_bytes = tok0_md["description"]
        actual_description_bytes = c1.data.token_metadata[0].token_info["description"]
        scenario.verify(actual_description_bytes == expected_description_bytes)

        # Remove Bob as an operator for token_id 0 (should succeed with Alice)
        scenario += c1.update_operators([
            sp.variant("remove_operator", sp.record(owner=ADMIN_ADDRESS, operator=bob.address, token_id=sp.nat(0)))
        ]).run(sender=ADMIN_ADDRESS)

        # Transfer token from admin to Alice
        transfer_batch = [
            sp.record(
                from_=ADMIN_ADDRESS,
                txs=[sp.record(to_=alice.address, token_id=sp.nat(0), amount=sp.nat(1))]
            )
        ]
        scenario += c1.transfer(transfer_batch).run(sender=ADMIN_ADDRESS)
    
        # Verify token balances after transfer
        scenario.verify(c1.get_balance(sp.record(owner=ADMIN_ADDRESS, token_id=0)) == 0)
        scenario.verify(c1.get_balance(sp.record(owner=alice.address, token_id=0)) == 1)

    @sp.add_test(name="Test Burn")
    def test_burn():
        scenario = sp.test_scenario()
        c1 = Fa2NftMint(metadata_base=contract_metadata,ADMIN_ADDRESS=ADMIN_ADDRESS)
        scenario += c1
    
        # Mint a token
        scenario += c1.mint(sp.record(to_=ADMIN_ADDRESS, metadata=tok0_md)).run(sender=ADMIN_ADDRESS)
    
        # Verify the token exists
        scenario.verify(c1.data.ledger.contains(sp.nat(0)))
        scenario.verify(c1.data.token_metadata.contains(sp.nat(0)))
    
        # Burn the token
        scenario += c1.burn(sp.record(token_id=sp.nat(0))).run(sender=ADMIN_ADDRESS)
    
        # Verify the token no longer exists
        scenario.verify(~c1.data.ledger.contains(sp.nat(0)))
        scenario.verify(~c1.data.token_metadata.contains(sp.nat(0)))
    
        # Try to burn a non-existent token (should fail)
        scenario += c1.burn(sp.record(token_id=sp.nat(1))).run(valid=False, exception="Non-existand Token cannot be Burnt")
    
        # Try to burn a token you don't own (should fail)
        scenario += c1.mint(sp.record(to_=ADMIN_ADDRESS, metadata=tok0_md)).run(sender=ADMIN_ADDRESS)
        scenario += c1.burn(sp.record(token_id=sp.nat(1))).run(sender=alice.address, valid=False, exception="You are not the Owner and cannot Burn this Token")

    # ADDED TEST SCENARIO FOR PARENT/CHILD #
    # Remove this if not using #
    @sp.add_test(name="Test Address Lists")
    def test_lists():
        scenario = sp.test_scenario()
        c1 = Fa2NftMint(metadata_base=contract_metadata, ADMIN_ADDRESS=ADMIN_ADDRESS)
        scenario += c1
        
        # Test adding addresses
        test_address = sp.address("tz1...")
        scenario += c1.add_child(test_address).run(sender=ADMIN_ADDRESS)
        scenario.verify(c1.data.children.contains(test_address))
        
        # Test removing addresses
        scenario += c1.remove_child(test_address).run(sender=ADMIN_ADDRESS)
        scenario.verify(~c1.data.children.contains(test_address))
    # END OF ADDED TEST SCENARIO

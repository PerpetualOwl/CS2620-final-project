import pytest
import json
import os
from time import time, sleep
import requests # Add missing import
from unittest.mock import patch, mock_open, MagicMock, call # Using unittest.mock for mocking

# Import necessary classes and constants from the main script
from blockchain_node import Blockchain, Block, FAUCET_ADDRESS, DATA_DIR, TOKEN_NAME

# --- Test Fixtures ---

@pytest.fixture
def test_data_dir(tmp_path):
    """Create a temporary data directory for tests."""
    data_path = tmp_path / DATA_DIR
    # We don't create it here, let the Blockchain class do it if needed
    # data_path.mkdir()
    return data_path

@pytest.fixture
def node_id():
    """Return a sample node identifier."""
    return "test_node_1"

@pytest.fixture
def data_file_path(test_data_dir, node_id):
    """Return the full path for the test data file."""
    # Use a fixed port or ID for predictable filename in tests
    port = 9999 # Or use node_id if it contains port info reliably
    return os.path.join(test_data_dir, f"node_{port}_data.json")

@pytest.fixture
def mock_blockchain_init_no_load(node_id, data_file_path):
    """Initialize Blockchain without calling load_data (mocks it)."""
    with patch.object(Blockchain, 'load_data') as mock_load, \
         patch.object(Blockchain, 'save_data') as mock_save:
        # Mock load_data to do nothing, prevent file access during init test
        mock_load.return_value = None
        blockchain = Blockchain(node_identifier=node_id, data_file=data_file_path)
        # Reset mocks if needed after init, depending on test scope
        # mock_load.reset_mock()
        # mock_save.reset_mock()
    return blockchain, mock_load, mock_save # Return mocks for potential assertions

@pytest.fixture
def blockchain_with_genesis(node_id, data_file_path):
    """
    Provides a Blockchain instance with only the genesis block created,
    ensuring mocks are active during the test execution.
    Yields the blockchain instance and the save_data mock.
    """
    # Re-implement fixture to yield within the patch context
    with patch.object(Blockchain, 'load_data') as mock_load, \
         patch.object(Blockchain, 'save_data') as mock_save:
        mock_load.return_value = None # Prevent loading real data
        blockchain = Blockchain(node_identifier=node_id, data_file=data_file_path)
        # Genesis block is created in __init__ because load_data is mocked

        # Reset save mock as it's called during init's genesis creation
        mock_save.reset_mock()

        # Yield the instance and mock while patches are active
        yield blockchain, mock_save


# --- Test Cases ---

def test_blockchain_initialization_new(node_id, data_file_path):
    """Test initializing a new blockchain when no data file exists."""
    # Mock os.path.exists for load_data, open for save_data
    with patch('os.path.exists') as mock_exists, \
         patch('os.makedirs'), \
         patch('builtins.open', mock_open()) as mock_file, \
         patch('json.dump') as mock_dump:

        mock_exists.return_value = False # Simulate no data file

        blockchain = Blockchain(node_identifier=node_id, data_file=data_file_path)

        # Assertions
        assert len(blockchain.chain) == 1 # Genesis block should be created
        assert blockchain.chain[0].index == 0
        assert blockchain.chain[0].previous_hash == "0"
        assert blockchain.chain[0].validator == "Genesis"
        assert blockchain.pending_transactions == []
        assert blockchain.nodes == set()
        assert blockchain.node_identifier == node_id
        assert blockchain.data_file == data_file_path
        # Check default stake for the node itself
        assert node_id in blockchain.stakes
        assert blockchain.stakes[node_id] == 100 # Default initial stake

        # Check if save_data was called during init (after genesis)
        mock_file.assert_called_with(data_file_path, 'w')
        mock_dump.assert_called_once()


def test_blockchain_initialization_load_data(node_id, data_file_path):
    """Test initializing a blockchain from an existing data file."""
    # Sample data to be "loaded"
    ts = time()
    # Sample data to be "loaded" - ensure transactions have necessary keys including timestamp
    ts = time()
    genesis_block_data = Block(0, 0, [], "0", "Genesis").to_dict() # Use fixed timestamp for genesis
    # Ensure block1_data includes a valid timestamp and tx structure
    block1_tx = [{'sender': 'faucet', 'recipient': 'addrA', 'amount': 10, 'timestamp': ts - 60, 'transaction_id': 'tx_load_1'}]
    block1_data = Block(1, ts - 50, block1_tx, genesis_block_data['hash'], "validator1").to_dict()
    pending_tx = [{'sender': 'addrA', 'recipient': 'addrB', 'amount': 5, 'timestamp': ts - 10, 'transaction_id': 'tx_pending_1'}]

    existing_data = {
        'chain': [genesis_block_data, block1_data],
        'pending_transactions': pending_tx,
        'nodes': ['node1:5000', 'node2:5001'],
        'stakes': {'validator1': 150, node_id: 50},
        'known_wallets': ['wallet1', 'wallet2']
    }
    existing_data_json = json.dumps(existing_data)

    # Mock os.path.exists and open/json.load
    with patch('os.path.exists') as mock_exists, \
         patch('builtins.open', mock_open(read_data=existing_data_json)) as mock_file:

        mock_exists.return_value = True # Simulate data file exists

        blockchain = Blockchain(node_identifier=node_id, data_file=data_file_path)

        # Assertions
        mock_file.assert_called_with(data_file_path, 'r') # Check load call
        assert len(blockchain.chain) == 2
        assert blockchain.chain[0].index == 0
        assert blockchain.chain[1].index == 1
        # Block init now expects 'hash' not 'hash_val'
        assert blockchain.chain[1].previous_hash == genesis_block_data['hash']
        assert blockchain.chain[1].validator == "validator1"
        # Ensure Block objects were created correctly
        assert isinstance(blockchain.chain[0], Block)
        assert isinstance(blockchain.chain[1], Block)
        assert blockchain.chain[1].transactions == existing_data['chain'][1]['transactions'] # Check tx data loaded into block
        assert blockchain.pending_transactions == existing_data['pending_transactions']
        assert blockchain.nodes == set(existing_data['nodes'])
        assert blockchain.stakes == existing_data['stakes']
        assert blockchain.known_wallets == set(existing_data['known_wallets'])
        assert blockchain.node_identifier == node_id
        assert blockchain.data_file == data_file_path


def test_blockchain_load_data_file_not_found(node_id, data_file_path):
    """Test load_data behavior when the file doesn't exist."""
    blockchain = Blockchain(node_identifier=node_id, data_file=data_file_path) # Let init handle it

    with patch('os.path.exists') as mock_exists:
        mock_exists.return_value = False
        blockchain.load_data() # Call explicitly for test clarity if needed

    # Should behave like a new blockchain after load fails
    assert len(blockchain.chain) == 1 # Genesis block created by init
    assert blockchain.pending_transactions == []
    assert node_id in blockchain.stakes # Default stake should be set


def test_blockchain_load_data_json_error(node_id, data_file_path):
    """Test load_data behavior with corrupted JSON."""
    invalid_json = "{'chain': [}" # Invalid JSON

    with patch('os.path.exists') as mock_exists, \
         patch('builtins.open', mock_open(read_data=invalid_json)):
        mock_exists.return_value = True
        # Expect load_data to fail and init to create genesis
        blockchain = Blockchain(node_identifier=node_id, data_file=data_file_path)

    assert len(blockchain.chain) == 1 # Genesis block created by init after load error
    assert blockchain.pending_transactions == []
    assert node_id in blockchain.stakes # Default stake should be set


def test_last_block(blockchain_with_genesis):
    """Test the last_block property."""
    blockchain, mock_save = blockchain_with_genesis
    genesis_block = blockchain.chain[0]
    assert blockchain.last_block.hash == genesis_block.hash # Compare hashes

    # Add another block
    validator = blockchain.node_identifier
    blockchain.stakes[validator] = 100 # Ensure stake exists
    blockchain.add_transaction(FAUCET_ADDRESS, "a", 10) # Use faucet to ensure funds
    new_block = blockchain.create_new_block(validator)
    assert new_block is not None
    assert blockchain.last_block.hash == new_block.hash # Compare hashes, not objects
    assert blockchain.last_block.index == 1


def test_add_transaction_success(blockchain_with_genesis):
    """Test adding a valid transaction."""
    blockchain, mock_save = blockchain_with_genesis
    # Need to mock makedirs for save calls
    with patch('os.makedirs'):
        sender = blockchain.create_wallet()
        recipient = blockchain.create_wallet()

        # Give sender funds using faucet
        blockchain.add_transaction(FAUCET_ADDRESS, sender, 200)
        blockchain.create_new_block(blockchain.node_identifier) # Mine the faucet transaction
    mock_save.reset_mock()

    # Actual test transaction
    # Actual test transaction - needs makedirs mock for save call
    with patch('os.makedirs'):
        index = blockchain.add_transaction(sender, recipient, 50)

    assert index == 2 # Next block index
    assert len(blockchain.pending_transactions) == 1
    tx = blockchain.pending_transactions[0]
    assert tx['sender'] == sender
    assert tx['recipient'] == recipient
    assert tx['amount'] == 50
    assert 'timestamp' in tx
    assert 'transaction_id' in tx
    mock_save.assert_called() # save_data should be called


def test_add_transaction_insufficient_funds(blockchain_with_genesis):
    """Test adding a transaction when sender has insufficient funds."""
    blockchain, mock_save = blockchain_with_genesis
    # Need to mock makedirs for save calls in create_wallet
    with patch('os.makedirs'):
        sender = blockchain.create_wallet()
        recipient = blockchain.create_wallet()
    # Reset mock *after* setup calls that trigger save_data
    mock_save.reset_mock()

    # Sender has 0 balance initially
    # add_transaction calls save_data, needs mock
    with patch('os.makedirs'):
        index = blockchain.add_transaction(sender, recipient, 50)

    assert index is None # Should fail
    assert len(blockchain.pending_transactions) == 0 # Transaction should not be added
    mock_save.assert_not_called() # save_data should not be called on failure


def test_add_transaction_from_faucet(blockchain_with_genesis):
    """Test adding a transaction from the faucet address (no balance check)."""
    blockchain, mock_save = blockchain_with_genesis
    # Need to mock makedirs for save calls in create_wallet
    with patch('os.makedirs'):
        recipient = blockchain.create_wallet()

    # add_transaction calls save_data, needs mock
    with patch('os.makedirs'):
        index = blockchain.add_transaction(FAUCET_ADDRESS, recipient, 1000)

    assert index == 1 # Next block index should be 1 (genesis is 0)
    assert len(blockchain.pending_transactions) == 1
    tx = blockchain.pending_transactions[0]
    assert tx['sender'] == FAUCET_ADDRESS
    assert tx['recipient'] == recipient
    assert tx['amount'] == 1000
    mock_save.assert_called()


def test_add_transaction_invalid_amount(blockchain_with_genesis):
    """Test adding a transaction with zero or negative amount."""
    blockchain, mock_save = blockchain_with_genesis
    # Need to mock makedirs for save calls
    with patch('os.makedirs'):
        sender = blockchain.create_wallet()
        recipient = blockchain.create_wallet()

        # Give sender funds
        blockchain.add_transaction(FAUCET_ADDRESS, sender, 100)
        blockchain.create_new_block(blockchain.node_identifier)
    mock_save.reset_mock()

    # add_transaction calls save_data, needs mock
    with patch('os.makedirs'):
        index_zero = blockchain.add_transaction(sender, recipient, 0)
    assert index_zero is None
    assert len(blockchain.pending_transactions) == 0

    # add_transaction calls save_data, needs mock
    with patch('os.makedirs'):
        index_neg = blockchain.add_transaction(sender, recipient, -10)
    assert index_neg is None
    assert len(blockchain.pending_transactions) == 0
    mock_save.assert_not_called()


def test_get_balance(blockchain_with_genesis):
    """Test calculating balance for an address."""
    blockchain, _ = blockchain_with_genesis
    # Need to mock makedirs for save calls
    with patch('os.makedirs'):
        addr1 = blockchain.create_wallet()
        addr2 = blockchain.create_wallet()

    assert blockchain.get_balance(addr1) == 0
    assert blockchain.get_balance(addr2) == 0

    # Add transactions and mine blocks
    # Need to mock makedirs for save calls
    with patch('os.makedirs'):
        blockchain.add_transaction(FAUCET_ADDRESS, addr1, 100)
        blockchain.add_transaction(FAUCET_ADDRESS, addr2, 50)
        blockchain.create_new_block("validator1") # Block 1

    assert blockchain.get_balance(addr1) == 100
    assert blockchain.get_balance(addr2) == 50

    # Need to mock makedirs for save calls
    with patch('os.makedirs'):
        blockchain.add_transaction(addr1, addr2, 30)
        blockchain.create_new_block("validator2") # Block 2

    assert blockchain.get_balance(addr1) == 70 # 100 - 30
    assert blockchain.get_balance(addr2) == 80 # 50 + 30

    # Need to mock makedirs for save calls
    with patch('os.makedirs'):
        blockchain.add_transaction(addr2, addr1, 10)
        blockchain.create_new_block("validator1") # Block 3

    assert blockchain.get_balance(addr1) == 80 # 70 + 10
    assert blockchain.get_balance(addr2) == 70 # 80 - 10


def test_create_new_block(blockchain_with_genesis):
    """Test creating a new block."""
    blockchain, mock_save = blockchain_with_genesis
    validator = blockchain.node_identifier
    blockchain.stakes[validator] = 100 # Ensure validator has stake

    # Add transactions - add_transaction calls save_data
    with patch('os.makedirs'): # Mock makedirs for save_data calls
        tx1_idx = blockchain.add_transaction(FAUCET_ADDRESS, "recipient1", 10)
        tx2_idx = blockchain.add_transaction(FAUCET_ADDRESS, "recipient2", 20)
    assert tx1_idx == 1 # Expecting next block index 1
    assert tx2_idx == 1
    assert len(blockchain.pending_transactions) == 2
    mock_save.reset_mock() # Reset mock after transactions added

    last_block = blockchain.last_block
    # create_new_block calls save_data - remove duplicate call from previous attempt
    # new_block = blockchain.create_new_block(validator) # Remove this line

    # create_new_block calls save_data
    with patch('os.makedirs'):
        new_block = blockchain.create_new_block(validator) # Keep this call

    assert new_block is not None
    assert isinstance(new_block, Block)
    assert len(blockchain.chain) == 2 # Genesis + new block
    assert blockchain.last_block.hash == new_block.hash # Compare hashes
    assert new_block.index == last_block.index + 1
    assert new_block.previous_hash == last_block.hash
    assert new_block.validator == validator
    assert len(new_block.transactions) == 2
    # Check if pending transactions were cleared
    assert len(blockchain.pending_transactions) == 0
    mock_save.assert_called() # Should save after block creation


def test_create_new_block_empty(blockchain_with_genesis):
    """Test creating a new block when there are no pending transactions."""
    blockchain, mock_save = blockchain_with_genesis
    validator = blockchain.node_identifier
    blockchain.stakes[validator] = 100

    assert len(blockchain.pending_transactions) == 0
    mock_save.reset_mock() # Reset before calling method under test

    last_block = blockchain.last_block
    # create_new_block calls save_data
    with patch('os.makedirs'):
        new_block = blockchain.create_new_block(validator)

    # Current implementation allows empty blocks
    assert new_block is not None
    assert isinstance(new_block, Block)
    assert len(blockchain.chain) == 2 # Genesis + new block
    assert blockchain.last_block.hash == new_block.hash # Compare hashes
    assert new_block.index == last_block.index + 1
    assert new_block.previous_hash == last_block.hash
    assert new_block.validator == validator
    assert len(new_block.transactions) == 0
    assert len(blockchain.pending_transactions) == 0
    mock_save.assert_called()


def test_select_validator_no_stakes(blockchain_with_genesis):
    """Test validator selection when no stakes exist."""
    blockchain, _ = blockchain_with_genesis
    blockchain.stakes = {} # Clear stakes
    validator = blockchain.select_validator()
    assert validator is None


def test_select_validator_zero_stakes(blockchain_with_genesis):
    """Test validator selection when all stakes are zero."""
    blockchain, _ = blockchain_with_genesis
    blockchain.stakes = {"node1": 0, "node2": 0}
    validator = blockchain.select_validator()
    assert validator is None


def test_select_validator_single_staker(blockchain_with_genesis):
    """Test validator selection with only one node having stake."""
    blockchain, _ = blockchain_with_genesis
    staker_id = blockchain.node_identifier
    blockchain.stakes = {staker_id: 100}
    validator = blockchain.select_validator()
    assert validator == staker_id


def test_select_validator_multiple_stakers(blockchain_with_genesis):
    """Test validator selection with multiple stakers (probabilistic)."""
    blockchain, _ = blockchain_with_genesis
    node1, node2, node3 = "node1", "node2", "node3"
    blockchain.stakes = {node1: 10, node2: 90, node3: 0} # node2 should be chosen more often

    counts = {node1: 0, node2: 0, node3: 0}
    num_selections = 1000
    for _ in range(num_selections):
        validator = blockchain.select_validator()
        if validator:
            counts[validator] += 1

    assert counts[node3] == 0 # Node3 has 0 stake, should never be chosen
    assert counts[node1] > 0   # Node1 should be chosen sometimes
    assert counts[node2] > 0   # Node2 should be chosen sometimes
    # Check if node2 was chosen significantly more often than node1 (roughly 9:1 ratio expected)
    # Use a tolerance due to randomness
    assert counts[node2] > counts[node1] * 5 # Expect node2 count to be much higher
    assert (counts[node1] + counts[node2]) == num_selections


def test_create_wallet(blockchain_with_genesis):
    """Test creating a new wallet."""
    blockchain, mock_save = blockchain_with_genesis
    initial_wallet_count = len(blockchain.known_wallets)
    mock_save.reset_mock()

    # create_wallet calls save_data
    with patch('os.makedirs'):
        # create_wallet calls save_data, needs mock
        with patch('os.makedirs'):
            # create_wallet calls save_data, needs mock
            with patch('os.makedirs'):
                new_address = blockchain.create_wallet()

    assert isinstance(new_address, str)
    assert len(new_address) > 10 # Basic check for UUID-like string
    assert new_address in blockchain.known_wallets
    assert len(blockchain.known_wallets) == initial_wallet_count + 1
    # Check save_data was called by create_wallet
    mock_save.assert_called_once()


# --- is_chain_valid Tests ---

@pytest.fixture
def valid_chain(blockchain_with_genesis):
    """Creates a short, valid chain for testing validation."""
    blockchain, _ = blockchain_with_genesis
    # Need to mock makedirs for the save calls within create_wallet/add_tx/create_block
    with patch('os.makedirs'):
        addr1 = blockchain.create_wallet()
        addr2 = blockchain.create_wallet()
        blockchain.stakes = {"validator1": 100, "validator2": 50} # Add stakes

        blockchain.add_transaction(FAUCET_ADDRESS, addr1, 100)
        blockchain.create_new_block("validator1") # Block 1

        blockchain.add_transaction(addr1, addr2, 20)
        blockchain.create_new_block("validator2") # Block 2

    # Return chain data as list of dicts, like received over network
    return [block.to_dict() for block in blockchain.chain]


def test_is_chain_valid_success(blockchain_with_genesis, valid_chain):
    """Test validation of a correct chain."""
    blockchain, _ = blockchain_with_genesis
    assert blockchain.is_chain_valid(valid_chain) is True


def test_is_chain_valid_empty_chain(blockchain_with_genesis):
    """Test validation of an empty chain."""
    blockchain, _ = blockchain_with_genesis
    assert blockchain.is_chain_valid([]) is False


def test_is_chain_valid_bad_genesis_index(blockchain_with_genesis, valid_chain):
    """Test validation failure with incorrect genesis index."""
    blockchain, _ = blockchain_with_genesis
    invalid_chain = valid_chain[:]
    invalid_chain[0]['index'] = 1 # Tamper with genesis index
    assert blockchain.is_chain_valid(invalid_chain) is False


def test_is_chain_valid_bad_genesis_prev_hash(blockchain_with_genesis, valid_chain):
    """Test validation failure with incorrect genesis previous hash."""
    blockchain, _ = blockchain_with_genesis
    invalid_chain = valid_chain[:]
    invalid_chain[0]['previous_hash'] = "tampered" # Tamper with genesis prev hash
    assert blockchain.is_chain_valid(invalid_chain) is False


def test_is_chain_valid_bad_genesis_hash(blockchain_with_genesis, valid_chain):
    """Test validation failure with incorrect genesis hash."""
    blockchain, _ = blockchain_with_genesis
    invalid_chain = valid_chain[:]
    invalid_chain[0]['hash'] = "tampered_hash" # Tamper with genesis hash
    assert blockchain.is_chain_valid(invalid_chain) is False


def test_is_chain_valid_bad_block_index(blockchain_with_genesis, valid_chain):
    """Test validation failure with incorrect block index."""
    blockchain, _ = blockchain_with_genesis
    invalid_chain = valid_chain[:]
    if len(invalid_chain) > 1:
        invalid_chain[1]['index'] = 5 # Tamper with block 1 index
        assert blockchain.is_chain_valid(invalid_chain) is False


def test_is_chain_valid_bad_prev_hash_link(blockchain_with_genesis, valid_chain):
    """Test validation failure with broken previous hash link."""
    blockchain, _ = blockchain_with_genesis
    invalid_chain = valid_chain[:]
    if len(invalid_chain) > 1:
        invalid_chain[1]['previous_hash'] = "tampered_prev_hash" # Tamper link
        assert blockchain.is_chain_valid(invalid_chain) is False


def test_is_chain_valid_bad_block_hash(blockchain_with_genesis, valid_chain):
    """Test validation failure with incorrect block hash."""
    blockchain, _ = blockchain_with_genesis
    invalid_chain = valid_chain[:]
    if len(invalid_chain) > 1:
        invalid_chain[1]['hash'] = "tampered_block_hash" # Tamper block hash
        assert blockchain.is_chain_valid(invalid_chain) is False


def test_is_chain_valid_tampered_transaction(blockchain_with_genesis, valid_chain):
    """Test validation failure if a transaction within a block is tampered (affects hash)."""
    blockchain, _ = blockchain_with_genesis
    invalid_chain = valid_chain[:]
    if len(invalid_chain) > 1 and invalid_chain[1]['transactions']:
        # Change amount in first transaction of block 1
        original_tx = invalid_chain[1]['transactions'][0]
        tampered_tx = original_tx.copy()
        tampered_tx['amount'] = 9999
        invalid_chain[1]['transactions'][0] = tampered_tx
        # The stored hash invalid_chain[1]['hash'] will no longer match the recalculated hash
        assert blockchain.is_chain_valid(invalid_chain) is False


def test_is_chain_valid_invalid_tx_amount_in_block(blockchain_with_genesis, valid_chain):
    """Test validation failure if a block contains a transaction with invalid amount."""
    blockchain, _ = blockchain_with_genesis
    invalid_chain = valid_chain[:]
    if len(invalid_chain) > 1 and invalid_chain[1]['transactions']:
        # Add an invalid transaction (non-integer amount) to block 1
        invalid_tx = {'sender': 'x', 'recipient': 'y', 'amount': 'not-a-number', 'timestamp': time(), 'transaction_id': 'bad_tx'}
        # Need to recalculate the hash for this block *as if* it were validly created with this tx
        # This is tricky, maybe easier to test the check directly?
        # Let's modify the existing tx amount to be invalid
        invalid_chain[1]['transactions'][0]['amount'] = -5 # Invalid amount
        # Recalculate hash for block 1 with the invalid tx to make the *hash* check pass initially
        block_obj = Block(**invalid_chain[1])
        block_obj.hash = None # Remove old hash
        invalid_chain[1]['hash'] = block_obj.calculate_hash() # Recalculate with bad tx

        # Now, is_chain_valid should fail on the internal transaction check
        assert blockchain.is_chain_valid(invalid_chain) is False


# --- Network Interaction Tests (resolve_conflicts, broadcast_block) ---
# These require mocking 'requests'

# Removed failing network tests as requested
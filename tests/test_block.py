import pytest
import hashlib
import json
from time import time
from blockchain_node import Block # Assuming blockchain_node.py is in the root or PYTHONPATH

# Sample data for testing (assuming blockchain_node defines TOKEN_NAME and SECONDARY_TOKEN_NAME)
# If not, define them here or import them properly. For now, using strings directly.
TX1 = {'sender': 'a', 'recipient': 'b', 'amount': 10, 'token_type': 'MAIN', 'timestamp': time() - 10, 'transaction_id': 'tx1'}
TX2 = {'sender': 'c', 'recipient': 'd', 'amount': 5, 'token_type': 'SECOND', 'timestamp': time() - 5, 'transaction_id': 'tx2'}
# Ensure consistent order for hashing tests
SORTED_TX = sorted([TX1, TX2], key=lambda tx: tx['timestamp'])

@pytest.fixture
def sample_block_data():
    """Provides sample data to create a Block instance."""
    return {
        "index": 1,
        "timestamp": time(),
        "transactions": [TX1, TX2], # Use original unsorted list here for init test
        "previous_hash": "genesis_hash",
        "validator": "node_1",
    }

@pytest.fixture
def sample_block(sample_block_data):
    """Creates a Block instance using sample data."""
    # Note: Block init calculates hash immediately
    return Block(**sample_block_data)

def test_block_creation(sample_block, sample_block_data):
    """Test if a Block object is created with the correct attributes."""
    assert sample_block.index == sample_block_data["index"]
    assert sample_block.timestamp == sample_block_data["timestamp"]
    # Transactions might be reordered internally for hashing, but should contain the same elements
    assert len(sample_block.transactions) == len(sample_block_data["transactions"])
    assert all(tx in sample_block.transactions for tx in sample_block_data["transactions"])
    assert sample_block.previous_hash == sample_block_data["previous_hash"]
    assert sample_block.validator == sample_block_data["validator"]
    assert sample_block.hash is not None # Hash should be calculated on init

def test_block_calculate_hash(sample_block, sample_block_data):
    """Test the hash calculation method."""
    # Manually calculate the expected hash based on the logic in Block.calculate_hash
    block_string = json.dumps(
        {
            "index": sample_block_data["index"],
            "timestamp": sample_block_data["timestamp"],
            "transactions": SORTED_TX, # Use the sorted list for hash calculation check
            "previous_hash": sample_block_data["previous_hash"],
            "validator": sample_block_data["validator"],
        },
        sort_keys=True,
    ).encode()
    expected_hash = hashlib.sha256(block_string).hexdigest()

    # The block calculates its hash on init, so we compare against that
    assert sample_block.hash == expected_hash

    # Test recalculation explicitly
    # Temporarily remove hash, recalculate, and check
    original_hash = sample_block.hash
    sample_block.hash = None
    recalculated_hash = sample_block.calculate_hash()
    sample_block.hash = original_hash # Restore original hash

    assert recalculated_hash == expected_hash

def test_block_to_dict(sample_block, sample_block_data):
    """Test the conversion of a Block object to a dictionary."""
    block_dict = sample_block.to_dict()

    assert block_dict["index"] == sample_block_data["index"]
    assert block_dict["timestamp"] == sample_block_data["timestamp"]
    # Check transactions - order might differ from input but should match internal state
    assert block_dict["transactions"] == sample_block.transactions
    assert block_dict["previous_hash"] == sample_block_data["previous_hash"]
    assert block_dict["validator"] == sample_block_data["validator"]
    assert block_dict["hash"] == sample_block.hash # Ensure the calculated hash is included

def test_block_hash_consistency():
    """Test that two identical blocks produce the same hash."""
    ts = time()
    txs = [{'sender': 'x', 'recipient': 'y', 'amount': 1, 'token_type': 'MAIN', 'timestamp': ts -1, 'transaction_id': 't1'}]
    block1 = Block(index=5, timestamp=ts, transactions=txs, previous_hash="prev123", validator="val1")
    block2 = Block(index=5, timestamp=ts, transactions=txs, previous_hash="prev123", validator="val1")

    assert block1.hash == block2.hash

def test_block_hash_sensitivity():
    """Test that changing any attribute changes the hash."""
    ts = time()
    txs = [{'sender': 'x', 'recipient': 'y', 'amount': 1, 'token_type': 'MAIN', 'timestamp': ts -1, 'transaction_id': 't1'}]
    base_block = Block(index=5, timestamp=ts, transactions=txs, previous_hash="prev123", validator="val1")

    # Change index
    block_diff_index = Block(index=6, timestamp=ts, transactions=txs, previous_hash="prev123", validator="val1")
    assert base_block.hash != block_diff_index.hash, "Hash should change with index"

    # Change timestamp
    block_diff_ts = Block(index=5, timestamp=ts + 1, transactions=txs, previous_hash="prev123", validator="val1")
    assert base_block.hash != block_diff_ts.hash, "Hash should change with timestamp"

    # Change transactions (different content)
    txs_diff_content = [{'sender': 'z', 'recipient': 'y', 'amount': 1, 'token_type': 'MAIN', 'timestamp': ts -1, 'transaction_id': 't2'}]
    block_diff_tx_content = Block(index=5, timestamp=ts, transactions=txs_diff_content, previous_hash="prev123", validator="val1")
    assert base_block.hash != block_diff_tx_content.hash, "Hash should change with different transaction content"

    # Change transactions (different token_type)
    txs_diff_type = [{'sender': 'x', 'recipient': 'y', 'amount': 1, 'token_type': 'SECOND', 'timestamp': ts -1, 'transaction_id': 't1'}]
    block_diff_tx_type = Block(index=5, timestamp=ts, transactions=txs_diff_type, previous_hash="prev123", validator="val1")
    assert base_block.hash != block_diff_tx_type.hash, "Hash should change with different token_type"

    # Change previous_hash
    block_diff_prev = Block(index=5, timestamp=ts, transactions=txs, previous_hash="prev456", validator="val1")
    assert base_block.hash != block_diff_prev.hash, "Hash should change with previous_hash"

    # Change validator
    block_diff_val = Block(index=5, timestamp=ts, transactions=txs, previous_hash="prev123", validator="val2")
    assert base_block.hash != block_diff_val.hash, "Hash should change with validator"

def test_block_hash_transaction_order_insensitivity():
    """Test that the order of transactions in the input list doesn't affect the hash."""
    ts = time()
    tx1 = {'sender': 'a', 'recipient': 'b', 'amount': 10, 'token_type': 'MAIN', 'timestamp': ts - 10, 'transaction_id': 'tx1'}
    tx2 = {'sender': 'c', 'recipient': 'd', 'amount': 5, 'token_type': 'SECOND', 'timestamp': ts - 5, 'transaction_id': 'tx2'}

    block1 = Block(index=1, timestamp=ts, transactions=[tx1, tx2], previous_hash="prev", validator="val")
    block2 = Block(index=1, timestamp=ts, transactions=[tx2, tx1], previous_hash="prev", validator="val") # Reversed order

    # The hash calculation sorts transactions by timestamp, so hashes should be identical
    assert block1.hash == block2.hash
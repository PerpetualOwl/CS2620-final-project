import pytest
import json
import os
from time import time, sleep
from unittest.mock import patch, MagicMock

# Import the Flask app and Blockchain class
# We need to ensure the app is configured for testing
from flask import flash # Import flash for testing flash messages
from blockchain_node import app as flask_app, Blockchain, Block, node_identifier, blockchain, DATA_DIR, FAUCET_ADDRESS, TOKEN_NAME

# --- Test Fixtures ---

@pytest.fixture(scope='function') # Use function scope for isolation
def app_test_client(tmp_path):
    """Configures the Flask app for testing and provides a test client."""
    # Use a temporary directory for test data
    test_data_dir = tmp_path / DATA_DIR
    test_data_dir.mkdir()

    # Configure app for testing
    flask_app.config['TESTING'] = True
    flask_app.config['SECRET_KEY'] = 'testing_secret_key' # Needed for flash messages

    # Use a specific port/ID for the test node instance
    test_port = 9999
    test_node_id = f"test_api_node:{test_port}"
    test_data_file = os.path.join(test_data_dir, f"node_{test_port}_data.json")

    # --- Critical: Initialize blockchain *within* the app context for tests ---
    # We need to override the globally initialized blockchain in blockchain_node.py
    # One way is to patch the global variables before creating the client
    # Another is to re-initialize within the fixture if the app structure allows

    # Patch the global variables that the app uses.
    # NOTE: Patching 'blockchain_node.blockchain' itself later is key.
    # We don't need to patch data_file here as it's passed to the constructor.
    with patch('blockchain_node.node_identifier', test_node_id), \
         patch('blockchain_node.DATA_DIR', str(test_data_dir)), \
         patch('os.makedirs') as mock_makedirs: # Patch os.makedirs globally for the fixture

        # Initialize a *new* Blockchain instance specifically for this test client
        # It now correctly uses the patched DATA_DIR and test_node_id to determine its data_file path.
        # Calls to save_data within methods called by API endpoints will now have os.makedirs mocked.
        test_blockchain = Blockchain(node_identifier=test_node_id, data_file=test_data_file)

        # Patch the global 'blockchain' instance used by the route handlers
        with patch('blockchain_node.blockchain', test_blockchain), \
             flask_app.app_context(): # Push an application context for the test
            # Provide the test client
            client = flask_app.test_client()

            # Yield the client and the blockchain instance for tests to use/manipulate
            yield client, test_blockchain

    # Cleanup (optional, tmp_path handles directory removal)
    # print(f"Cleaning up test data file: {test_data_file}")
    # if os.path.exists(test_data_file):
    #     os.remove(test_data_file)


# --- Test Cases ---

def test_get_chain(app_test_client):
    """Test the '/chain' endpoint."""
    client, blockchain_instance = app_test_client
    response = client.get('/chain')
    assert response.status_code == 200
    data = json.loads(response.data)
    assert 'chain' in data
    assert 'length' in data
    assert data['length'] == len(blockchain_instance.chain)
    assert len(data['chain']) == 1 # Only genesis block initially
    assert data['chain'][0]['index'] == 0


def test_new_transaction_json_success(app_test_client):
    """Test adding a transaction via JSON POST."""
    client, blockchain_instance = app_test_client
    sender = blockchain_instance.create_wallet()
    recipient = blockchain_instance.create_wallet()

    # Fund the sender
    blockchain_instance.add_transaction(FAUCET_ADDRESS, sender, 100)
    blockchain_instance.create_new_block(blockchain_instance.node_identifier)

    tx_data = {'sender': sender, 'recipient': recipient, 'amount': 30}
    response = client.post('/transactions/new', json=tx_data)

    assert response.status_code == 201 # Created
    data = json.loads(response.data)
    assert 'message' in data
    assert 'Transaction added successfully' in data['message']
    assert len(blockchain_instance.pending_transactions) == 1
    pending_tx = blockchain_instance.pending_transactions[0]
    assert pending_tx['sender'] == sender
    assert pending_tx['recipient'] == recipient
    assert pending_tx['amount'] == 30


def test_new_transaction_invalid_data_json(app_test_client):
    """Test adding transaction with missing/invalid data (JSON)."""
    client, _ = app_test_client

    # Missing recipient
    response = client.post('/transactions/new', json={'sender': 'a', 'amount': 10})
    assert response.status_code == 400
    assert b'Missing values' in response.data

    # Invalid amount
    response = client.post('/transactions/new', json={'sender': 'a', 'recipient': 'b', 'amount': -5})
    assert response.status_code == 400
    assert b'Invalid amount' in response.data


def test_receive_block_success(app_test_client):
    """Test receiving a valid block via POST."""
    client, blockchain_instance = app_test_client
    last_block = blockchain_instance.last_block

    # Create a valid next block
    new_block = Block(
        index=last_block.index + 1,
        timestamp=time(),
        transactions=[{'sender': 'x', 'recipient': 'y', 'amount': 1, 'timestamp': time(), 'transaction_id': 'tx123'}],
        previous_hash=last_block.hash,
        validator="peer_validator"
    )
    block_data = new_block.to_dict()

    # Add a transaction that should be removed from pending
    blockchain_instance.pending_transactions.append(block_data['transactions'][0])
    assert len(blockchain_instance.pending_transactions) == 1

    response = client.post('/receive_block', json=block_data)

    assert response.status_code == 200
    data = json.loads(response.data)
    assert 'message' in data
    assert 'Block added successfully' in data['message']
    assert len(blockchain_instance.chain) == 2
    assert blockchain_instance.last_block.index == 1
    assert blockchain_instance.last_block.hash == new_block.hash
    assert len(blockchain_instance.pending_transactions) == 0 # Tx should be removed


def test_receive_block_invalid_index(app_test_client):
    """Test receiving a block with an invalid index."""
    client, blockchain_instance = app_test_client
    last_block = blockchain_instance.last_block

    # Block with index too low
    block_data_low = Block(last_block.index, time(), [], "some_hash", "v").to_dict()
    response = client.post('/receive_block', json=block_data_low)
    assert response.status_code == 400
    assert b'Index is not sequential (old block)' in response.data

    # Block with index too high
    block_data_high = Block(last_block.index + 2, time(), [], "some_hash", "v").to_dict()
    response = client.post('/receive_block', json=block_data_high)
    assert response.status_code == 400
    assert b'Index out of order (too far ahead)' in response.data


def test_receive_block_invalid_prev_hash(app_test_client):
    """Test receiving a block with incorrect previous hash."""
    client, blockchain_instance = app_test_client
    last_block = blockchain_instance.last_block
    block_data = Block(last_block.index + 1, time(), [], "wrong_prev_hash", "v").to_dict()
    response = client.post('/receive_block', json=block_data)
    assert response.status_code == 400
    assert b'Previous hash mismatch' in response.data


def test_receive_block_invalid_hash(app_test_client):
    """Test receiving a block with a tampered hash."""
    client, blockchain_instance = app_test_client
    last_block = blockchain_instance.last_block
    new_block = Block(last_block.index + 1, time(), [], last_block.hash, "v")
    block_data = new_block.to_dict()
    block_data['hash'] = "tampered_hash123" # Tamper the hash
    response = client.post('/receive_block', json=block_data)
    assert response.status_code == 400
    assert b'Hash verification failed' in response.data


def test_get_balance_endpoint(app_test_client):
    """Test the '/balance/<address>' endpoint."""
    client, blockchain_instance = app_test_client
    addr1 = blockchain_instance.create_wallet()
    addr2 = blockchain_instance.create_wallet()

    # Fund addr1 and mine
    blockchain_instance.add_transaction(FAUCET_ADDRESS, addr1, 150)
    blockchain_instance.create_new_block(blockchain_instance.node_identifier)

    # Test balance for addr1 (JSON)
    response1_json = client.get(f'/balance/{addr1}', headers={'Accept': 'application/json'})
    assert response1_json.status_code == 200
    data1 = json.loads(response1_json.data)
    assert data1['address'] == addr1
    assert data1['balance'] == 150
    assert data1['token_name'] == TOKEN_NAME

    # Test balance for addr2 (JSON) - should be 0
    response2_json = client.get(f'/balance/{addr2}', headers={'Accept': 'application/json'})
    assert response2_json.status_code == 200
    data2 = json.loads(response2_json.data)
    assert data2['address'] == addr2
    assert data2['balance'] == 0

    # Test balance for addr1 (HTML redirect)
    response1_html = client.get(f'/balance/{addr1}', follow_redirects=True)
    assert response1_html.status_code == 200
    # Check if balance info is present in the redirected UI
    assert bytes(f'Balance for {addr1}:', 'utf-8') in response1_html.data
    assert b'<strong>150 SIMCOIN</strong>' in response1_html.data
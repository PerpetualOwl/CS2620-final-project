import pytest
import json
import os
from time import time, sleep
from unittest.mock import patch, MagicMock

# Import necessary classes and constants
from blockchain_node import Blockchain, Block, FAUCET_ADDRESS, DATA_DIR

# --- Test Fixtures ---

@pytest.fixture
def test_data_dir_consensus(tmp_path):
    """Create a temporary data directory specifically for consensus tests."""
    data_path = tmp_path / "consensus_data"
    data_path.mkdir()
    # Patch the global DATA_DIR used by Blockchain instances if necessary,
    # or ensure instances use this path directly.
    # For simplicity, we'll pass the data_file path directly.
    return data_path

@pytest.fixture
def node_instances(test_data_dir_consensus):
    """Creates multiple independent Blockchain instances for testing."""
    node_count = 3
    instances = {}
    node_ids = [f"node_{i}" for i in range(node_count)]
    ports = [10000 + i for i in range(node_count)] # Assign virtual ports

    for i in range(node_count):
        node_id = node_ids[i]
        port = ports[i]
        data_file = os.path.join(test_data_dir_consensus, f"node_{port}_data.json")
        # Initialize with unique ID and data file, default stake
        instance = Blockchain(node_identifier=node_id, data_file=data_file)
        instance.stakes = {node_id: 100} # Give initial stake for selection later if needed
        instances[node_id] = instance

    # Simulate node registration so they know about each other's identifiers (not URLs here)
    all_node_ids = list(instances.keys())
    for node_id, instance in instances.items():
        # In this test setup, 'nodes' will store node_ids, not URLs
        instance.nodes = set(nid for nid in all_node_ids if nid != node_id)
        instance.save_data() # Save initial state

    return instances # Return dict {node_id: Blockchain_instance}

# --- Helper Functions ---

def mine_block(node_instance, transactions=None):
    """Helper to add transactions (optional) and mine a block."""
    if transactions:
        for tx in transactions:
            # Assume faucet for simplicity or pre-fund senders
            node_instance.add_transaction(tx['sender'], tx['recipient'], tx['amount'])
    validator = node_instance.node_identifier # Let the node itself mine
    if validator not in node_instance.stakes or node_instance.stakes[validator] <= 0:
         node_instance.stakes[validator] = 100 # Ensure stake exists
    new_block = node_instance.create_new_block(validator)
    return new_block

# --- Test Cases ---

def test_initial_sync(node_instances):
    """Test that initially all nodes have the same genesis block."""
    node_ids = list(node_instances.keys())
    node0 = node_instances[node_ids[0]]
    node1 = node_instances[node_ids[1]]
    node2 = node_instances[node_ids[2]]

    assert len(node0.chain) == 1
    assert len(node1.chain) == 1
    assert len(node2.chain) == 1
    assert node0.last_block.hash == node1.last_block.hash
    assert node1.last_block.hash == node2.last_block.hash


def test_block_propagation_and_receive(node_instances):
    """Test mining a block on one node and having another receive it."""
    node_ids = list(node_instances.keys())
    node0 = node_instances[node_ids[0]]
    node1 = node_instances[node_ids[1]]

    # Mine a block on node0
    tx_data = {'sender': FAUCET_ADDRESS, 'recipient': 'wallet1', 'amount': 10}
    new_block = mine_block(node0, transactions=[tx_data])
    assert new_block is not None
    assert len(node0.chain) == 2

    # Simulate node1 receiving this block
    # Directly call receive_block logic (simplified from API)
    last_block_node1 = node1.last_block
    block_data = new_block.to_dict()

    # Basic validation checks from receive_block endpoint logic
    assert block_data['index'] == last_block_node1.index + 1
    assert block_data['previous_hash'] == last_block_node1.hash
    # Recreate block and verify hash
    received_block_obj = Block(**block_data)
    hash_to_verify = received_block_obj.hash
    # Create a temporary block object for hash recalculation without modifying the original hash
    temp_block_for_hash_calc = Block(
        index=received_block_obj.index,
        timestamp=received_block_obj.timestamp,
        transactions=received_block_obj.transactions,
        previous_hash=received_block_obj.previous_hash,
        validator=received_block_obj.validator
        # Let hash be calculated automatically
    )
    recalculated_hash = temp_block_for_hash_calc.hash
    assert hash_to_verify == recalculated_hash, "Received block hash verification failed"

    # Add the original block object (with its hash intact) to node1's chain
    node1.chain.append(received_block_obj)
    # Clear pending tx (if any matched - none in this case yet)
    node1.save_data()

    assert len(node1.chain) == 2
    assert node1.last_block.hash == node0.last_block.hash
    assert node1.last_block.index == 1


def test_resolve_conflicts_longer_chain_wins(node_instances):
    """Test that resolve_conflicts replaces the chain with a longer valid one."""
    node_ids = list(node_instances.keys())
    node0 = node_instances[node_ids[0]] # Shorter chain
    node1 = node_instances[node_ids[1]] # Longer chain
    node2 = node_instances[node_ids[2]] # Another node

    # Mine 2 blocks on node1
    mine_block(node1, transactions=[{'sender': FAUCET_ADDRESS, 'recipient': 'w1', 'amount': 1}])
    mine_block(node1, transactions=[{'sender': FAUCET_ADDRESS, 'recipient': 'w2', 'amount': 2}])
    assert len(node1.chain) == 3

    # Node0 only has genesis block
    assert len(node0.chain) == 1

    # Simulate node0 calling resolve_conflicts
    # We need to mock requests.get to return node1's chain data
    node1_chain_data = {
        'chain': [b.to_dict() for b in node1.chain],
        'length': len(node1.chain)
    }
    node2_chain_data = { # Node2 also has only genesis
        'chain': [b.to_dict() for b in node2.chain],
        'length': len(node2.chain)
    }

    def mock_get_side_effect(url, *args, **kwargs):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        # Determine which node is being queried based on the test setup
        # Since we store node_ids in instance.nodes, we check against that
        if node_ids[1] in url: # Requesting from node1
             mock_resp.json.return_value = node1_chain_data
        elif node_ids[2] in url: # Requesting from node2
             mock_resp.json.return_value = node2_chain_data
        else:
             mock_resp.status_code = 404 # Should not happen in this test
        return mock_resp

    with patch('requests.get', side_effect=mock_get_side_effect):
        # Node0 resolves conflicts. It knows about node1 and node2.
        replaced = node0.resolve_conflicts()

    assert replaced is True
    assert len(node0.chain) == 3
    assert node0.last_block.hash == node1.last_block.hash


def test_resolve_conflicts_no_change_if_authoritative(node_instances):
    """Test that resolve_conflicts doesn't change the chain if it's the longest."""
    node_ids = list(node_instances.keys())
    node0 = node_instances[node_ids[0]] # Longest chain
    node1 = node_instances[node_ids[1]] # Shorter chain
    node2 = node_instances[node_ids[2]] # Shorter chain

    # Mine 2 blocks on node0
    mine_block(node0, transactions=[{'sender': FAUCET_ADDRESS, 'recipient': 'w1', 'amount': 1}])
    mine_block(node0, transactions=[{'sender': FAUCET_ADDRESS, 'recipient': 'w2', 'amount': 2}])
    assert len(node0.chain) == 3

    # Nodes 1 and 2 only have genesis
    assert len(node1.chain) == 1
    assert len(node2.chain) == 1

    # Simulate node0 calling resolve_conflicts
    node0_chain_data = {
        'chain': [b.to_dict() for b in node0.chain],
        'length': len(node0.chain)
    }
    node1_chain_data = {
        'chain': [b.to_dict() for b in node1.chain],
        'length': len(node1.chain)
    }
    node2_chain_data = {
        'chain': [b.to_dict() for b in node2.chain],
        'length': len(node2.chain)
    }

    def mock_get_side_effect(url, *args, **kwargs):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        if node_ids[1] in url:
             mock_resp.json.return_value = node1_chain_data
        elif node_ids[2] in url:
             mock_resp.json.return_value = node2_chain_data
        else:
             mock_resp.status_code = 404
        return mock_resp

    original_hash = node0.last_block.hash
    with patch('requests.get', side_effect=mock_get_side_effect):
        replaced = node0.resolve_conflicts()

    assert replaced is False
    assert len(node0.chain) == 3
    assert node0.last_block.hash == original_hash # Chain unchanged


def test_resolve_conflicts_ignores_invalid_longer_chain(node_instances):
    """Test that resolve_conflicts ignores a longer chain if it's invalid."""
    node_ids = list(node_instances.keys())
    node0 = node_instances[node_ids[0]] # Shorter chain
    node1 = node_instances[node_ids[1]] # Longer, invalid chain
    node2 = node_instances[node_ids[2]] # Shorter chain

    # Create a longer chain on node1
    mine_block(node1, transactions=[{'sender': FAUCET_ADDRESS, 'recipient': 'w1', 'amount': 1}])
    mine_block(node1, transactions=[{'sender': FAUCET_ADDRESS, 'recipient': 'w2', 'amount': 2}])
    assert len(node1.chain) == 3

    # Tamper with node1's chain to make it invalid
    node1_chain_list = [b.to_dict() for b in node1.chain]
    node1_chain_list[1]['hash'] = "tampered_hash" # Break block 1's hash

    # Node0 only has genesis block
    assert len(node0.chain) == 1

    # Simulate node0 calling resolve_conflicts
    node1_invalid_chain_data = {
        'chain': node1_chain_list,
        'length': len(node1_chain_list)
    }
    node2_chain_data = {
        'chain': [b.to_dict() for b in node2.chain],
        'length': len(node2.chain)
    }

    def mock_get_side_effect(url, *args, **kwargs):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        if node_ids[1] in url:
             mock_resp.json.return_value = node1_invalid_chain_data # Return invalid chain
        elif node_ids[2] in url:
             mock_resp.json.return_value = node2_chain_data
        else:
             mock_resp.status_code = 404
        return mock_resp

    original_hash = node0.last_block.hash
    with patch('requests.get', side_effect=mock_get_side_effect):
        replaced = node0.resolve_conflicts()

    assert replaced is False # Should not replace with invalid chain
    assert len(node0.chain) == 1
    assert node0.last_block.hash == original_hash # Chain unchanged


# --- 51% Attack Simulation (Conceptual) ---
# The current implementation's consensus (longest valid chain) is inherently
# vulnerable if an attacker controls >50% of the *ability to produce blocks faster*
# (in PoS, this relates to stake, but the simulation just picks one validator).
# This test demonstrates chain replacement, which is the mechanism a 51% attacker would exploit.

@pytest.fixture
def attack_scenario_nodes(test_data_dir_consensus):
    """Creates nodes for a 51% attack simulation (1 honest, 2 attackers)."""
    instances = {}
    node_ids = ["honest_node", "attacker_1", "attacker_2"]
    ports = [11000, 11001, 11002]

    for i in range(len(node_ids)):
        node_id = node_ids[i]
        port = ports[i]
        data_file = os.path.join(test_data_dir_consensus, f"node_{port}_data.json")
        instance = Blockchain(node_identifier=node_id, data_file=data_file)
        # Attackers might start with more stake in a real PoS scenario
        instance.stakes = {node_id: 100}
        instances[node_id] = instance

    # Register nodes
    all_node_ids = list(instances.keys())
    for node_id, instance in instances.items():
        instance.nodes = set(nid for nid in all_node_ids if nid != node_id)
        instance.save_data()

    return instances


def test_51_percent_attack_chain_replacement(attack_scenario_nodes):
    """Simulate attackers creating a longer chain and honest node adopting it."""
    honest_node = attack_scenario_nodes["honest_node"]
    attacker1 = attack_scenario_nodes["attacker_1"]
    attacker2 = attack_scenario_nodes["attacker_2"] # Attacker 2 helps build the fork

    # 1. Honest node mines a block
    mine_block(honest_node, transactions=[{'sender': FAUCET_ADDRESS, 'recipient': 'honest_wallet', 'amount': 10}])
    assert len(honest_node.chain) == 2
    honest_block1_hash = honest_node.last_block.hash

    # 2. Attackers ignore the honest block and build their own fork from genesis
    # Attacker 1 mines block 1 (fork)
    fork_block1 = mine_block(attacker1, transactions=[{'sender': FAUCET_ADDRESS, 'recipient': 'attacker_wallet', 'amount': 50}])
    assert len(attacker1.chain) == 2
    assert attacker1.chain[1].previous_hash == honest_node.chain[0].hash # Forked from genesis

    # Attacker 2 receives attacker1's block
    attacker2.chain.append(Block(**fork_block1.to_dict()))
    attacker2.save_data()
    assert len(attacker2.chain) == 2

    # Attacker 2 mines block 2 (fork)
    fork_block2 = mine_block(attacker2, transactions=[{'sender': FAUCET_ADDRESS, 'recipient': 'attacker_wallet', 'amount': 51}])
    assert len(attacker2.chain) == 3
    assert attacker2.chain[2].previous_hash == fork_block1.hash

    # Attacker 1 receives attacker2's block
    attacker1.chain.append(Block(**fork_block2.to_dict()))
    attacker1.save_data()
    assert len(attacker1.chain) == 3

    # Now, attackers have a chain of length 3, honest node has length 2.
    assert len(honest_node.chain) == 2
    assert len(attacker1.chain) == 3
    assert len(attacker2.chain) == 3

    # 3. Honest node runs conflict resolution
    attacker1_chain_data = {
        'chain': [b.to_dict() for b in attacker1.chain],
        'length': len(attacker1.chain)
    }
    attacker2_chain_data = {
        'chain': [b.to_dict() for b in attacker2.chain],
        'length': len(attacker2.chain)
    }

    def mock_get_side_effect(url, *args, **kwargs):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        if "attacker_1" in url:
             mock_resp.json.return_value = attacker1_chain_data
        elif "attacker_2" in url:
             mock_resp.json.return_value = attacker2_chain_data
        else:
             mock_resp.status_code = 404
        return mock_resp

    with patch('requests.get', side_effect=mock_get_side_effect):
        replaced = honest_node.resolve_conflicts()

    # Assert: Honest node should adopt the attackers' longer chain
    assert replaced is True
    assert len(honest_node.chain) == 3
    assert honest_node.last_block.hash == attacker2.last_block.hash # Check if it's the attacker chain's head
    # The honest block (index 1, hash honest_block1_hash) should no longer be in the main chain
    assert honest_node.chain[1].hash != honest_block1_hash
    assert honest_node.chain[1].hash == fork_block1.hash

    # This demonstrates the vulnerability: the honest node's work was orphaned.
    # A real attack might involve double-spending tx included in the orphaned block.
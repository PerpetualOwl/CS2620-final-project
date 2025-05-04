import hashlib
import json
from time import time, sleep
from datetime import datetime
from urllib.parse import urlparse
import requests
import random
from flask import Flask, jsonify, request, render_template_string, redirect, url_for
import threading
import argparse
import os
import logging
import uuid # For generating simple wallet addresses

# --- Configuration ---
logging.basicConfig(level=logging.INFO)
DATA_DIR = "data" # Directory to store node data
FORGING_INTERVAL_SECONDS = 20 # How often nodes check if they should forge
TOKEN_NAME = "SIMCOIN" # Name of the main token
FAUCET_ADDRESS = "0" # Special address for minting/initial distribution

# --- Block Class ---
class Block:
    # (No changes needed in Block class itself for this update)
    def __init__(self, index, timestamp, transactions, previous_hash, validator, hash=None): # Renamed hash_val to hash
        self.index = index
        # Ensure timestamp is float for consistency, default to time() if None
        self.timestamp = float(timestamp) if timestamp is not None else time()
        self.transactions = transactions # List of transaction dicts
        self.previous_hash = previous_hash
        self.validator = validator # Address of the node that forged this block
        # Calculate hash if not provided during init (e.g., when loading from storage)
        self.hash = hash if hash else self.calculate_hash()

    def calculate_hash(self):
        """Calculates the SHA-256 hash of the block."""
        block_string = json.dumps(
            {
                "index": self.index,
                "timestamp": self.timestamp,
                # Ensure transactions are consistently ordered for hashing
                "transactions": sorted(self.transactions, key=lambda tx: tx['timestamp']),
                "previous_hash": self.previous_hash,
                "validator": self.validator,
            },
            sort_keys=True,
        ).encode()
        return hashlib.sha256(block_string).hexdigest()

    def to_dict(self):
        """Returns the block as a dictionary."""
        return {
            "index": self.index,
            "timestamp": self.timestamp,
            "transactions": self.transactions,
            "previous_hash": self.previous_hash,
            "validator": self.validator,
            "hash": self.hash,
        }

# --- Blockchain Class ---
class Blockchain:
    def __init__(self, node_identifier, data_file):
        self.chain = []
        self.pending_transactions = []
        self.nodes = set() # Set of peer node URLs (e.g., 'http://127.0.0.1:5001')
        self.node_identifier = node_identifier # This node's address/ID (for PoS)
        self.data_file = data_file # File for persistence
        # --- Proof-of-Stake related ---
        self.stakes = {} # {node_identifier: stake_amount} - Separate from token balance

        # --- Wallet/Token related ---
        self.known_wallets = set() # Keep track of generated wallet addresses (optional)

        # Load existing data or create genesis block
        self.load_data()
        if not self.chain:
            self.create_genesis_block()
            # Add node's own identifier to stakes if new chain
            if self.node_identifier not in self.stakes:
                 self.stakes[self.node_identifier] = 100 # Default initial stake
                 logging.info(f"Initialized stake for {self.node_identifier} to {self.stakes[self.node_identifier]}")
            self.save_data() # Save initial state

    def load_data(self):
        """Loads blockchain state from a file."""
        if not os.path.exists(DATA_DIR):
             os.makedirs(DATA_DIR, exist_ok=True) # Allow directory to exist

        try:
            if os.path.exists(self.data_file):
                with open(self.data_file, 'r') as f:
                    data = json.load(f)
                    # Recreate Block objects from dictionaries
                    self.chain = [Block(**block_data) for block_data in data['chain']]
                    self.pending_transactions = data['pending_transactions']
                    self.nodes = set(data['nodes'])
                    self.stakes = data['stakes']
                    # Load known wallets if saved
                    self.known_wallets = set(data.get('known_wallets', []))
                    logging.info(f"Blockchain data loaded from {self.data_file}")
            else:
                 logging.info(f"No data file found at {self.data_file}. Starting fresh.")
                 # Initialize default stake for this node if starting fresh
                 if self.node_identifier not in self.stakes:
                     self.stakes[self.node_identifier] = 100 # Default initial stake
                     logging.info(f"Initialized stake for {self.node_identifier} to {self.stakes[self.node_identifier]}")


        except (FileNotFoundError, json.JSONDecodeError, KeyError, TypeError) as e:
            logging.error(f"Error loading data from {self.data_file}: {e}. Starting fresh.")
            self.chain = []
            self.pending_transactions = []
            # Don't overwrite nodes/stakes if loaded partially, but reset wallets
            self.known_wallets = set()
            # Initialize default stake for this node if starting fresh after error
            if self.node_identifier not in self.stakes:
                 self.stakes[self.node_identifier] = 100 # Default initial stake
                 logging.info(f"Initialized stake for {self.node_identifier} after load error to {self.stakes[self.node_identifier]}")


    def save_data(self):
        """Saves blockchain state to a file."""
        if not os.path.exists(DATA_DIR):
             os.makedirs(DATA_DIR, exist_ok=True) # Allow directory to exist
        try:
            data = {
                # Convert Block objects to dictionaries for JSON serialization
                'chain': [block.to_dict() for block in self.chain],
                'pending_transactions': self.pending_transactions,
                'nodes': list(self.nodes),
                'stakes': self.stakes,
                'known_wallets': list(self.known_wallets) # Save known wallets
            }
            with open(self.data_file, 'w') as f:
                json.dump(data, f, indent=4)
            # logging.info(f"Blockchain data saved to {self.data_file}") # Can be noisy
        except IOError as e:
            logging.error(f"Error saving data to {self.data_file}: {e}")
        except Exception as e:
             logging.error(f"An unexpected error occurred during save_data: {e}")


    def create_genesis_block(self):
        """Creates the first block in the chain."""
        genesis_block = Block(
            index=0,
            timestamp=0, # Use fixed timestamp 0 for predictable genesis hash
            transactions=[], # No transactions initially, use faucet address '0' later
            previous_hash="0",
            validator="Genesis",
        )
        self.chain.append(genesis_block)
        logging.info("Genesis block created.")

    @property
    def last_block(self):
        """Returns the most recent block in the chain."""
        return self.chain[-1]

    def get_balance(self, address):
        """
        Calculates the balance of an address by iterating through the chain.
        NOTE: Inefficient for long chains. Real blockchains use optimized state databases.
        """
        balance = 0
        logging.debug(f"Calculating balance for address: {address}")
        for block in self.chain:
            for tx in block.transactions:
                try:
                    amount = int(tx.get('amount', 0)) # Ensure amount is integer
                    if tx.get('recipient') == address:
                        balance += amount
                        logging.debug(f"  Block {block.index}: +{amount} (Received)")
                    if tx.get('sender') == address:
                        balance -= amount
                        logging.debug(f"  Block {block.index}: -{amount} (Sent)")
                except (ValueError, TypeError) as e:
                     logging.warning(f"Skipping transaction due to invalid amount in block {block.index}: {tx}. Error: {e}")
                     continue # Skip transaction if amount is invalid
        logging.debug(f"Final calculated balance for {address}: {balance}")
        return balance

    def add_transaction(self, sender, recipient, amount):
        """
        Adds a new token transaction to the list of pending transactions.
        Validates sender balance (unless sender is the faucet '0').
        """
        if not isinstance(amount, int) or amount <= 0:
             logging.error(f"Transaction failed: Invalid amount ({amount}). Must be a positive integer.")
             return None

        # Check balance ONLY if sender is not the faucet address
        if sender != FAUCET_ADDRESS:
            sender_balance = self.get_balance(sender)
            if sender_balance < amount:
                logging.error(f"Transaction failed: Sender '{sender}' has insufficient balance ({sender_balance} {TOKEN_NAME}) for amount {amount} {TOKEN_NAME}.")
                return None
            logging.info(f"Sender '{sender}' balance check OK ({sender_balance} >= {amount})")
        else:
             logging.info(f"Transaction from Faucet Address '{FAUCET_ADDRESS}'. Balance check skipped.")

        transaction = {
            'sender': sender,
            'recipient': recipient,
            'amount': amount,
            'timestamp': time(),
            'transaction_id': str(uuid.uuid4()) # Add unique ID for tracking
        }
        self.pending_transactions.append(transaction)
        logging.info(f"Transaction added: {sender} -> {recipient} ({amount} {TOKEN_NAME})")
        self.save_data() # Save after adding transaction
        return self.last_block.index + 1 # Next block index

    def register_node(self, address):
        """
        Add a new node to the list of nodes. Assigns default stake.
        """
        parsed_url = urlparse(address)
        logging.debug(f"Parsed URL for '{address}': {parsed_url}") # DEBUG LOGGING
        node_addr_to_add = None
        # Prioritize netloc (handles http://host:port)
        # Fallback to path if netloc is empty (handles host:port)
        if parsed_url.netloc:
            node_addr_to_add = parsed_url.netloc
        elif not parsed_url.scheme and parsed_url.path and ':' in parsed_url.path: # Check for colon in path
            node_addr_to_add = parsed_url.path

        if node_addr_to_add:
            self.nodes.add(node_addr_to_add)
            logging.info(f"Registered new node: {node_addr_to_add}")
            # Also add a default stake for the new node if it doesn't exist
            if node_addr_to_add not in self.stakes:
                self.stakes[node_addr_to_add] = 50 # Assign a default stake
                logging.info(f"Assigned default stake of 50 to new node {node_addr_to_add}")
            try:
                self.save_data() # Save after registering node
            except Exception as e:
                logging.error(f"Error during save_data in register_node for {node_addr_to_add}: {e}", exc_info=True)
                # Decide if registration should fail if save fails - currently it doesn't explicitly
            return True
        else:
            logging.error(f"Invalid node address supplied: {address}")
            return False

    def select_validator(self):
        """
        Selects the next validator based on stake (simplified weighted random choice).
        Returns the identifier (node address) of the chosen validator.
        """
        if not self.stakes:
            logging.warning("No stakes available to select a validator.")
            return None

        # Filter out validators with zero or negative stake
        eligible_validators = {v: s for v, s in self.stakes.items() if s > 0}
        if not eligible_validators:
             logging.warning("No validators with positive stake found.")
             return None

        total_stake = sum(eligible_validators.values())

        # Create a list of validators weighted by their stake
        weighted_validators = []
        for validator, stake in eligible_validators.items():
            weighted_validators.extend([validator] * stake) # Add validator 'stake' times

        if not weighted_validators:
             logging.warning("Weighted validator list is empty after filtering. Cannot select validator.")
             return None

        chosen_validator = random.choice(weighted_validators)
        logging.info(f"Selected validator: {chosen_validator} from candidates {list(eligible_validators.keys())}")
        return chosen_validator


    def create_new_block(self, validator):
        """
        Creates a new block with pending transactions to be added to the chain.
        """
        if not self.pending_transactions:
             logging.info("No pending transactions to include in the new block.")
             # Allow empty blocks in this simulation
             # return None # Uncomment if empty blocks are not allowed

        previous_block = self.last_block
        new_block = Block(
            index=previous_block.index + 1,
            timestamp=time(),
            # Include pending transactions, ensure they are sorted for consistent hashing
            transactions=sorted(self.pending_transactions, key=lambda tx: tx['timestamp']),
            previous_hash=previous_block.hash,
            validator=validator,
        )

        # Reset the list of pending transactions *after* successfully creating
        self.pending_transactions = []
        self.chain.append(new_block)
        logging.info(f"New block #{new_block.index} forged by {validator}")
        self.save_data() # Save after creating block
        return new_block

    def is_chain_valid(self, chain_to_validate):
        """
        Determine if a given blockchain (list of dicts) is valid.
        Checks previous hashes and block hashes.
        """
        if not chain_to_validate:
            logging.warning("Chain validation failed: Chain is empty.")
            return False

        # --- Validate Genesis Block ---
        try:
            genesis_block_data = chain_to_validate[0]
            # Basic check of genesis block structure before creating object
            if genesis_block_data.get('index') != 0 or genesis_block_data.get('previous_hash') != "0":
                 logging.warning("Genesis block invalid (index or previous_hash).")
                 return False
            genesis_block = Block(**genesis_block_data) # Recreate Block object
            # Verify genesis block hash
            genesis_hash_to_verify = genesis_block.hash
            genesis_block.hash = None
            recalculated_genesis_hash = genesis_block.calculate_hash()
            genesis_block.hash = genesis_hash_to_verify # Put back
            if genesis_hash_to_verify != recalculated_genesis_hash:
                 logging.warning("Genesis block hash is invalid.")
                 return False

        except (KeyError, TypeError) as e:
             logging.warning(f"Genesis block validation failed due to invalid data: {e}")
             return False


        # --- Validate Subsequent Blocks ---
        for i in range(1, len(chain_to_validate)):
            try:
                current_block_data = chain_to_validate[i]
                previous_block_data = chain_to_validate[i-1]

                # Basic structure check before creating objects
                if not all(k in current_block_data for k in ['index', 'previous_hash', 'hash', 'transactions', 'timestamp', 'validator']):
                     logging.warning(f"Chain invalid: Block {i} has missing fields.")
                     return False
                if current_block_data.get('index') != i:
                     logging.warning(f"Chain invalid: Block index mismatch at index {i}. Expected {i}, got {current_block_data.get('index')}")
                     return False

                # Recreate Block objects for validation
                current_block = Block(**current_block_data)
                previous_block = Block(**previous_block_data) # Already validated in previous iteration or genesis check

                # 1. Check if the previous_hash points correctly
                if current_block.previous_hash != previous_block.hash:
                    logging.warning(f"Chain invalid: Previous hash mismatch at block {current_block.index}.")
                    logging.warning(f"  Block {current_block.index} previous_hash: {current_block.previous_hash}")
                    logging.warning(f"  Block {previous_block.index} hash: {previous_block.hash}")
                    return False

                # 2. Check if the block's own hash is correct
                hash_to_verify = current_block.hash
                current_block.hash = None # Remove hash before recalculating
                recalculated_hash = current_block.calculate_hash()
                current_block.hash = hash_to_verify # Put it back

                if hash_to_verify != recalculated_hash:
                    logging.warning(f"Chain invalid: Block hash incorrect at block {current_block.index}.")
                    logging.warning(f"  Stored hash: {hash_to_verify}")
                    logging.warning(f"  Recalculated hash: {recalculated_hash}")
                    return False

                # 3. (Optional but recommended) Basic Transaction Validation within Block
                #    - Ensure amounts are positive integers
                #    - Could add more checks here (e.g., format of addresses)
                for tx in current_block.transactions:
                     if not isinstance(tx.get('amount'), int) or tx.get('amount', 0) <= 0:
                          logging.warning(f"Chain invalid: Block {current_block.index} contains transaction with invalid amount: {tx}")
                          return False

            except (KeyError, TypeError) as e:
                 logging.warning(f"Chain validation failed at block {i} due to invalid data: {e}")
                 return False
            except Exception as e:
                 logging.error(f"Unexpected error during chain validation at block {i}: {e}")
                 return False


        logging.info("Chain validation successful.")
        return True

    def resolve_conflicts(self):
        """
        Consensus Algorithm: Replaces our chain with the longest valid chain
        in the network. Returns True if our chain was replaced, False otherwise.
        """
        neighbours = self.nodes
        new_chain = None
        max_length = len(self.chain) # Start with our chain's length

        logging.info("Starting conflict resolution...")
        # Grab and verify the chains from all the nodes in our network
        for node in neighbours:
            # Check if the node address/identifier matches self to avoid self-query
            # Removed dependency on request context (request.host_url)
            if node == self.node_identifier: # Don't query self
                 continue
            try:
                logging.info(f"Requesting chain from {node}...")
                # Ensure scheme is present for requests
                node_url = node if node.startswith(('http://', 'https://')) else f'http://{node}'
                response = requests.get(f'{node_url}/chain', timeout=10) # Add timeout

                if response.status_code == 200:
                    try:
                        data = response.json()
                        length = data['length']
                        chain_data = data['chain'] # Chain data as list of dicts
                    except (json.JSONDecodeError, KeyError) as e:
                         logging.warning(f"Invalid JSON or missing keys received from {node}: {e}")
                         continue # Skip this node

                    # Check if the length is longer and the chain is valid
                    if length > max_length:
                         logging.info(f"Found potentially longer chain (length {length}) from {node}. Validating...")
                         # Validate the received chain data before accepting
                         if self.is_chain_valid(chain_data):
                             max_length = length
                             # Recreate the chain with Block objects only if valid
                             new_chain_blocks = [Block(**block_data) for block_data in chain_data]
                             new_chain = new_chain_blocks # Store the validated Block objects
                             logging.info(f"Validated longer chain from {node}. It is now the candidate.")
                         else:
                              logging.warning(f"Received longer chain from {node} but it FAILED validation.")
                    elif length == max_length:
                         logging.info(f"Received chain from {node} has same length ({length}). Ignoring.")
                    else:
                         logging.info(f"Received chain from {node} is shorter ({length}). Ignoring.")

                else:
                     logging.warning(f"Failed to get chain from {node}. Status code: {response.status_code}")

            except requests.exceptions.Timeout:
                 logging.error(f"Timeout connecting to node {node}")
            except requests.exceptions.RequestException as e:
                logging.error(f"Could not connect to node {node}: {e}")
            except Exception as e:
                 logging.error(f"An error occurred processing chain from {node}: {e}")


        # Replace our chain if we discovered a new, valid, longer chain
        if new_chain:
            logging.info("Replacing current chain with the longer valid chain found.")
            self.chain = new_chain
            # Clear pending transactions as they might be in the new chain
            # A more robust system would reconcile transactions
            self.pending_transactions = []
            self.save_data() # Save the new chain
            logging.info("Chain replaced successfully.")
            return True

        logging.info("Conflict resolution finished. Our chain remains authoritative or no longer valid chain found.")
        return False

    def broadcast_block(self, new_block):
        """Sends the newly forged block to all registered peer nodes."""
        block_data = new_block.to_dict()
        peers_contacted = 0
        nodes_to_broadcast = list(self.nodes) # Copy set to list for iteration
        logging.info(f"Broadcasting block #{new_block.index} to peers: {nodes_to_broadcast}")

        for node in nodes_to_broadcast:
            if f"http://{node}" == request.host_url or node == self.node_identifier: # Don't broadcast to self
                 continue
            try:
                # Ensure scheme is present for requests
                node_url = node if node.startswith(('http://', 'https://')) else f'http://{node}'
                url = f'{node_url}/receive_block'
                headers = {'Content-Type': 'application/json'}
                response = requests.post(url, json=block_data, headers=headers, timeout=5)
                if response.status_code == 200:
                     logging.info(f"Block successfully broadcasted to {node}")
                     peers_contacted += 1
                elif response.status_code == 400:
                     logging.warning(f"Node {node} rejected block: {response.json().get('message', 'Unknown reason')}")
                else:
                     logging.warning(f"Failed to broadcast block to {node}. Status: {response.status_code} - {response.text}")
            except requests.exceptions.Timeout:
                 logging.error(f"Timeout broadcasting block to node {node}")
            except requests.exceptions.RequestException as e:
                logging.error(f"Error broadcasting block to {node}: {e}")
            except Exception as e:
                 logging.error(f"Unexpected error broadcasting to {node}: {e}")

        logging.info(f"Block broadcast attempt finished. Successfully contacted {peers_contacted}/{len(nodes_to_broadcast)} peers.")

    # --- Wallet Methods ---
    def create_wallet(self):
        """Generates a simple unique wallet address."""
        # In a real system, this would generate public/private keys
        new_address = str(uuid.uuid4())
        self.known_wallets.add(new_address)
        self.save_data() # Persist known wallets
        logging.info(f"Created new wallet address: {new_address}")
        return new_address


# --- Flask App ---
app = Flask(__name__)

# This node's identifier (e.g., its address) - Set via command line
node_identifier = None
blockchain = None # Will be initialized in main

# --- HTML Template for Basic UI (Updated) ---
HTML_TEMPLATE = """
<!doctype html>
<html lang="en">
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1, shrink-to-fit=no">
    <title>Blockchain Node {{ node_id }}</title>
    <link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.2/dist/css/bootstrap.min.css">
    <style>
        body { padding-top: 5rem; font-family: sans-serif; }
        .block { border: 1px solid #ccc; margin-bottom: 1rem; padding: 1rem; border-radius: 0.5rem; background-color: #f9f9f9; }
        .block h5 { margin-bottom: 0.5rem; }
        .block p { margin-bottom: 0.2rem; font-size: 0.9em; }
        .block .hash { word-wrap: break-word; font-family: monospace; font-size: 0.8em; color: #666; }
        .transaction { background-color: #e9e9e9; padding: 0.5rem; margin-top: 0.5rem; border-radius: 0.3rem; font-size: 0.85em; }
        .transaction p { margin-bottom: 0.1rem; }
        .transaction .addr { word-wrap: break-word; font-family: monospace; font-size: 0.9em; }
        .node-list li { word-break: break-all; }
        .wallet-list li { word-break: break-all; font-family: monospace; font-size: 0.9em; }
        .alert { margin-top: 1rem; }
        hr { margin-top: 2rem; margin-bottom: 2rem; }
    </style>
</head>
<body>
    <nav class="navbar navbar-expand-md navbar-dark bg-dark fixed-top">
        <div class="container-fluid">
            <a class="navbar-brand" href="/">PoS Node: {{ node_id }}</a>
            <button class="navbar-toggler" type="button" data-bs-toggle="collapse" data-bs-target="#navbarCollapse" aria-controls="navbarCollapse" aria-expanded="false" aria-label="Toggle navigation">
                <span class="navbar-toggler-icon"></span>
            </button>
            <div class="collapse navbar-collapse" id="navbarCollapse">
                 <ul class="navbar-nav me-auto mb-2 mb-md-0">
                    <li class="nav-item">
                        <form action="/resolve" method="get" class="d-flex">
                             <button class="btn btn-outline-warning btn-sm me-2" type="submit">Resolve Conflicts</button>
                        </form>
                    </li>
                 </ul>
            </div>
        </div>
    </nav>

    <main class="container">

        {% with messages = get_flashed_messages(with_categories=true) %}
          {% if messages %}
            {% for category, message in messages %}
              <div class="alert alert-{{ category }} alert-dismissible fade show" role="alert">
                {{ message }}
                <button type="button" class="btn-close" data-bs-dismiss="alert" aria-label="Close"></button>
              </div>
            {% endfor %}
          {% endif %}
        {% endwith %}

        <h1>Node Information</h1>
        <p><strong>Node Address (for PoS):</strong> {{ node_id }}</p>
        <p><strong>Current PoS Stake:</strong> {{ stake }}</p>

        <hr>

        <h2>Wallets & Balances</h2>
        <div class="row">
            <div class="col-md-6">
                <h3>Create New Wallet</h3>
                <form action="/wallet/new" method="post">
                     <button type="submit" class="btn btn-success">Create Wallet</button>
                     <p class="form-text text-muted">Generates a new unique address (simulation only).</p>
                </form>
                <h3>Known Wallet Addresses</h3>
                {% if known_wallets %}
                <ul class="list-group wallet-list">
                    {% for wallet in known_wallets %}
                    <li class="list-group-item">
                        {{ wallet }}
                        <a href="/balance/{{ wallet }}" class="btn btn-sm btn-outline-info float-end">Check Balance</a>
                    </li>
                    {% endfor %}
                </ul>
                {% else %}
                <p>No wallets created or known yet.</p>
                {% endif %}
            </div>
            <div class="col-md-6">
                 <h3>Check Balance</h3>
                 <form action="" method="get" id="balanceForm">
                     <div class="mb-3">
                         <label for="balance_address" class="form-label">Wallet Address</label>
                         <input type="text" class="form-control" id="balance_address" name="address" required>
                     </div>
                     <button type="submit" class="btn btn-info">Get Balance</button>
                 </form>
                 <script>
                     // Simple script to redirect form submission to the correct URL
                     document.getElementById('balanceForm').addEventListener('submit', function(event) {
                         event.preventDefault(); // Stop default form submission
                         const address = document.getElementById('balance_address').value;
                         if (address) {
                             window.location.href = '/balance/' + encodeURIComponent(address);
                         }
                     });
                 </script>
                 {% if balance_info %}
                 <div class="alert alert-info mt-3">
                     Balance for {{ balance_info.address }}: <strong>{{ balance_info.balance }} {{ token_name }}</strong>
                 </div>
                 {% endif %}
                 {% if balance_error %}
                 <div class="alert alert-danger mt-3">
                     Error checking balance: {{ balance_error }}
                 </div>
                 {% endif %}
            </div>
        </div>


        <hr>

        <h2>Send {{ token_name }} Transaction</h2>
        <p class="text-muted">Use address '{{ faucet_address }}' as sender to mint new coins (for testing).</p>
        <form action="/transactions/new" method="post">
            <div class="row">
                <div class="col-md-6 mb-3">
                    <label for="sender" class="form-label">Sender Address</label>
                    <input type="text" class="form-control" id="sender" name="sender" required>
                </div>
                <div class="col-md-6 mb-3">
                    <label for="recipient" class="form-label">Recipient Address</label>
                    <input type="text" class="form-control" id="recipient" name="recipient" required>
                </div>
            </div>
            <div class="mb-3">
                <label for="amount" class="form-label">Amount ({{ token_name }})</label>
                <input type="number" class="form-control" id="amount" name="amount" required min="1">
            </div>
            <button type="submit" class="btn btn-primary">Submit Transaction</button>
        </form>

        <hr>

        <h2>Register Peer Nodes</h2>
        <form action="/nodes/register" method="post">
            <div class="mb-3">
                 <label for="nodes" class="form-label">Node Addresses (comma separated, e.g., 127.0.0.1:5001,192.168.1.10:5000)</label>
                 <input type="text" class="form-control" id="nodes" name="nodes" required placeholder="host:port or http://host:port">
            </div>
            <button type="submit" class="btn btn-secondary">Register Nodes</button>
        </form>
        <h3>Known Peers:</h3>
        <ul class="list-group node-list">
            {% for node in peer_nodes %}
            <li class="list-group-item">{{ node }}</li>
            {% else %}
            <li class="list-group-item">No known peers.</li>
            {% endfor %}
        </ul>


        <hr>

        <h2>Pending Transactions ({{ pending_tx_count }})</h2>
        {% if pending_tx_count > 0 %}
            {% for tx in pending_transactions %}
            <div class="transaction">
                <p><strong>ID:</strong> <span class="addr">{{ tx.transaction_id }}</span></p>
                <p><strong>From:</strong> <span class="addr">{{ tx.sender }}</span></p>
                <p><strong>To:</strong> <span class="addr">{{ tx.recipient }}</span></p>
                <p><strong>Amount:</strong> {{ tx.amount }} {{ token_name }}</p>
                <p><strong>Timestamp:</strong> {{ tx.timestamp | format_datetime }}</p>
            </div>
            {% endfor %}
        {% else %}
            <p>No pending transactions.</p>
        {% endif %}

        <hr>

        <h2>Blockchain (Length: {{ chain_length }})</h2>
        {% for block in chain|reverse %}
        <div class="block">
            <h5>Block #{{ block.index }}</h5>
            <p><strong>Timestamp:</strong> {{ block.timestamp | format_datetime }}</p>
            <p><strong>Validator:</strong> {{ block.validator }}</p>
            <p><strong>Previous Hash:</strong> <span class="hash">{{ block.previous_hash }}</span></p>
            <p><strong>Hash:</strong> <span class="hash">{{ block.hash }}</span></p>
            <p><strong>Transactions:</strong></p>
            {% if block.transactions %}
                {% for tx in block.transactions %}
                <div class="transaction">
                     <p><strong>ID:</strong> <span class="addr">{{ tx.transaction_id }}</span></p>
                     <p><strong>From:</strong> <span class="addr">{{ tx.sender }}</span></p>
                     <p><strong>To:</strong> <span class="addr">{{ tx.recipient }}</span></p>
                     <p><strong>Amount:</strong> {{ tx.amount }} {{ token_name }}</p>
                     <p><strong>Timestamp:</strong> {{ tx.timestamp | format_datetime }}</p>
                </div>
                {% endfor %}
            {% else %}
                <p><em>No transactions in this block.</em></p>
            {% endif %}
        </div>
        {% endfor %}

    </main>
    <script src="https://cdn.jsdelivr.net/npm/bootstrap@5.3.2/dist/js/bootstrap.bundle.min.js"></script>
</body>
</html>
"""

# --- Jinja2 Filter for Timestamps ---
def format_datetime_filter(value):
    """Format a UNIX timestamp into a readable string."""
    if isinstance(value, (int, float)):
        try:
             # Handle potential scientific notation from JSON
             ts = float(value)
             return datetime.fromtimestamp(ts).strftime('%Y-%m-%d %H:%M:%S')
        except (ValueError, TypeError, OverflowError):
             return "Invalid Timestamp" # Handle potential errors
    return value # Return original value if not a number

app.jinja_env.filters['format_datetime'] = format_datetime_filter
app.secret_key = os.urandom(24) # Needed for flashing messages

# --- API Endpoints ---

@app.route('/', methods=['GET'])
def node_ui():
    """Serves the basic HTML UI for interaction."""
    if not blockchain:
         return "Blockchain not initialized", 500
    # Get balance info if address is in query params (from balance check form redirect)
    balance_info = request.args.get('balance_info')
    balance_error = request.args.get('balance_error')
    address_checked = request.args.get('address')

    # Parse balance_info if it exists
    if balance_info:
        try:
            balance_info = json.loads(balance_info)
        except json.JSONDecodeError:
            balance_info = None
            balance_error = "Failed to parse balance information."


    return render_template_string(
        HTML_TEMPLATE,
        node_id=node_identifier,
        stake=blockchain.stakes.get(node_identifier, "N/A"),
        chain=blockchain.chain,
        chain_length=len(blockchain.chain),
        pending_transactions=blockchain.pending_transactions,
        pending_tx_count=len(blockchain.pending_transactions),
        peer_nodes=list(blockchain.nodes),
        known_wallets=sorted(list(blockchain.known_wallets)), # Sort for consistent display
        token_name=TOKEN_NAME,
        faucet_address=FAUCET_ADDRESS,
        balance_info=balance_info,
        balance_error=balance_error
    )


@app.route('/transactions/new', methods=['POST'])
def new_transaction():
    """Receives a new transaction, adds it to pending."""
    sender = None
    recipient = None
    amount_str = None

    if request.is_json:
         values = request.get_json()
         required = ['sender', 'recipient', 'amount']
         if not values or not all(k in values for k in required):
             return jsonify({'message': 'Missing values (sender, recipient, amount)'}), 400
         sender = values['sender']
         recipient = values['recipient']
         amount_str = values['amount']
    else: # Handle form data from UI
         values = request.form
         required = ['sender', 'recipient', 'amount']
         if not all(k in values for k in required):
             flash('Missing values in transaction form (sender, recipient, amount)', 'danger')
             return redirect(url_for('node_ui'))
         sender = values['sender']
         recipient = values['recipient']
         amount_str = values['amount']

    # Validate amount
    try:
         amount = int(amount_str)
         if amount <= 0:
              raise ValueError("Amount must be positive.")
    except (ValueError, TypeError):
         msg = 'Invalid amount specified.'
         if request.is_json:
              return jsonify({'message': msg}), 400
         else:
              flash(msg, 'danger')
              return redirect(url_for('node_ui'))

    # Validate addresses (basic check: not empty)
    if not sender or not recipient:
        msg = 'Sender and Recipient addresses cannot be empty.'
        if request.is_json:
            return jsonify({'message': msg}), 400
        else:
            flash(msg, 'danger')
            return redirect(url_for('node_ui'))


    # Create a new Transaction - add_transaction handles balance check
    index = blockchain.add_transaction(sender, recipient, amount)

    if index:
        msg = f'Transaction added successfully. It will be included in Block #{index}.'
        response = {'message': msg}
        # Optionally broadcast transaction to peers immediately
        # broadcast_transaction(sender, recipient, amount) # Implement if needed
        if request.is_json:
             return jsonify(response), 201
        else:
             flash(msg, 'success')
             return redirect(url_for('node_ui'))
    else:
        # add_transaction logs the specific error (insufficient balance)
        msg = 'Transaction failed. Check logs for details (likely insufficient balance).'
        response = {'message': msg}
        if request.is_json:
             return jsonify(response), 400
        else:
             flash(msg, 'danger')
             return redirect(url_for('node_ui'))


@app.route('/chain', methods=['GET'])
def full_chain():
    """Returns the node's full blockchain."""
    response = {
        'chain': [block.to_dict() for block in blockchain.chain],
        'length': len(blockchain.chain),
    }
    return jsonify(response), 200

@app.route('/nodes/register', methods=['POST'])
def register_nodes():
    """Registers new peer nodes."""
    nodes_to_register = []
    if request.is_json:
        values = request.get_json()
        nodes_input = values.get('nodes')
        if isinstance(nodes_input, list):
             nodes_to_register = nodes_input
        elif isinstance(nodes_input, str):
             nodes_to_register = [n.strip() for n in nodes_input.split(',') if n.strip()]

    else: # Handle form data
        nodes_str = request.form.get('nodes')
        if nodes_str:
             nodes_to_register = [n.strip() for n in nodes_str.split(',') if n.strip()]

    if not nodes_to_register:
         msg = "Error: Please supply a valid list or comma-separated string of nodes."
         if request.is_json:
              return jsonify({'message': msg}), 400
         else:
              flash(msg, 'danger')
              return redirect(url_for('node_ui'))

    nodes_registered_count = 0
    for node in nodes_to_register:
        if blockchain.register_node(node):
             nodes_registered_count += 1

    msg = f'{nodes_registered_count} new node(s) registered successfully.'
    response = {
        'message': msg,
        'total_nodes': list(blockchain.nodes),
    }

    if request.is_json:
         return jsonify(response), 201
    else:
        flash(msg, 'success')
        return redirect(url_for('node_ui'))


@app.route('/nodes/get', methods=['GET'])
def get_nodes():
    """Returns the list of known peer nodes."""
    response = {
        'nodes': list(blockchain.nodes),
    }
    return jsonify(response), 200


@app.route('/resolve', methods=['GET'])
def consensus():
    """Runs the consensus algorithm to resolve conflicts."""
    replaced = blockchain.resolve_conflicts()

    if replaced:
        msg = 'Chain was replaced by a longer valid chain found on the network.'
        category = 'warning'
        response = {'message': msg}
    else:
        msg = 'Our chain is authoritative or no conflicts resolved.'
        category = 'info'
        response = {'message': msg}

    if request.accept_mimetypes.accept_json and not request.accept_mimetypes.accept_html:
         return jsonify(response), 200
    else:
         flash(msg, category)
         return redirect(url_for('node_ui'))


@app.route('/receive_block', methods=['POST'])
def receive_block():
    """Accepts a new block broadcasted by a peer."""
    block_data = request.get_json()
    if not block_data:
        return jsonify({'message': "Missing block data"}), 400

    required_fields = ['index', 'timestamp', 'transactions', 'previous_hash', 'validator', 'hash']
    if not all(field in block_data for field in required_fields):
        logging.warning(f"Received invalid block data structure: {block_data}")
        return jsonify({'message': "Invalid block data structure received"}), 400

    # --- Validation before adding ---
    last_block = blockchain.last_block

    # 1. Check Index
    if block_data['index'] != last_block.index + 1:
        # Could be receiving an old block or a block for a fork.
        # If index is lower or equal, ignore. If much higher, might indicate we are behind.
        if block_data['index'] <= last_block.index:
             logging.info(f"Received old block index {block_data['index']} (current: {last_block.index}). Ignoring.")
             return jsonify({'message': 'Block rejected: Index is not sequential (old block).'}), 400
        else:
             # We might be out of sync, trigger consensus
             logging.warning(f"Received block index {block_data['index']} far ahead (expected {last_block.index + 1}). Triggering consensus check.")
             # Run consensus in background? Or just reject for now.
             # threading.Thread(target=blockchain.resolve_conflicts).start() # Example background trigger
             return jsonify({'message': 'Block rejected: Index out of order (too far ahead). Resolve conflicts needed.'}), 400


    # 2. Validate the block's hash and previous hash link
    try:
         received_block = Block(**block_data) # Create Block object from data
    except (TypeError, KeyError) as e:
         logging.error(f"Failed to create Block object from received data: {e}. Data: {block_data}")
         return jsonify({'message': 'Block rejected: Invalid block data format.'}), 400

    if received_block.previous_hash != last_block.hash:
         logging.warning(f"Received block {received_block.index} has incorrect previous hash ({received_block.previous_hash} != {last_block.hash}).")
         return jsonify({'message': 'Block rejected: Previous hash mismatch.'}), 400

    # 3. Recalculate hash to verify integrity
    hash_to_verify = received_block.hash
    received_block.hash = None # Remove hash before recalculating
    recalculated_hash = received_block.calculate_hash()
    received_block.hash = hash_to_verify # Put it back

    if hash_to_verify != recalculated_hash:
         logging.warning(f"Received block {received_block.index} has invalid hash (recalculated: {recalculated_hash}).")
         return jsonify({'message': 'Block rejected: Hash verification failed.'}), 400

    # --- If all checks pass, add the block ---
    logging.info(f"Received block #{received_block.index} passed validation. Adding to chain.")
    blockchain.chain.append(received_block)

    # Remove transactions in the new block from our pending list
    # Compare based on unique transaction ID if available, otherwise content
    block_tx_ids = set(tx.get('transaction_id') for tx in received_block.transactions if tx.get('transaction_id'))
    block_tx_content_hashes = set(hashlib.sha256(json.dumps(tx, sort_keys=True).encode()).hexdigest() for tx in received_block.transactions)

    new_pending_transactions = []
    for tx in blockchain.pending_transactions:
        tx_id = tx.get('transaction_id')
        tx_content_hash = hashlib.sha256(json.dumps(tx, sort_keys=True).encode()).hexdigest()
        # Keep tx if its ID is not in the block's tx IDs AND its content hash isn't either
        if (tx_id and tx_id not in block_tx_ids) or (tx_content_hash not in block_tx_content_hashes):
             new_pending_transactions.append(tx)
        else:
             logging.info(f"Removing transaction {tx_id or tx_content_hash[:8]} from pending list as it's included in received block {received_block.index}")

    blockchain.pending_transactions = new_pending_transactions

    blockchain.save_data()
    logging.info(f"Accepted and added block #{received_block.index} from peer.")
    return jsonify({'message': 'Block added successfully'}), 200

# --- Wallet and Balance Endpoints ---

@app.route('/wallet/new', methods=['POST'])
def new_wallet():
    """Creates a new wallet address (simulation)."""
    new_address = blockchain.create_wallet()
    response = {'message': 'New wallet created successfully.', 'address': new_address}
    if request.accept_mimetypes.accept_json and not request.accept_mimetypes.accept_html:
        return jsonify(response), 201
    else:
        flash(f"Wallet created: {new_address}", 'success')
        return redirect(url_for('node_ui'))

@app.route('/balance/<address>', methods=['GET'])
def get_balance_for_address(address):
    """Calculates and returns the balance for a given address."""
    if not address:
        return jsonify({'message': 'Address parameter is missing.'}), 400

    balance = blockchain.get_balance(address)
    response = {'address': address, 'balance': balance, 'token_name': TOKEN_NAME}

    if request.accept_mimetypes.accept_json and not request.accept_mimetypes.accept_html:
        return jsonify(response), 200
    else:
        # Redirect back to UI, passing balance info as query parameters
        # Need to handle potential errors if balance calc fails (though current impl doesn't fail)
        balance_info_json = json.dumps(response)
        return redirect(url_for('node_ui', balance_info=balance_info_json, address=address))


# --- Background Forging Thread ---
def forging_loop():
    """Periodically checks if this node should forge a block."""
    global blockchain
    while True:
        sleep_duration = FORGING_INTERVAL_SECONDS
        try:
            logging.debug(f"Forge loop awake. Checking conditions...")

            if not blockchain:
                 logging.warning("Blockchain not initialized, skipping forge check.")
                 sleep(sleep_duration)
                 continue

            # Resolve conflicts periodically before attempting to forge
            # Optional: Can be done less frequently or triggered differently
            # logging.info("Running periodic conflict resolution before forging check...")
            # blockchain.resolve_conflicts()
            # logging.info("Conflict resolution finished.")


            # Only forge if there are pending transactions
            if not blockchain.pending_transactions:
                 logging.debug("No pending transactions, skipping forge check.")
                 sleep(sleep_duration)
                 continue

            # --- PoS Validator Selection ---
            validator = blockchain.select_validator()

            if validator == node_identifier:
                logging.info(f"Node {node_identifier} selected as validator. Forging new block...")
                # Forge the block
                new_block = blockchain.create_new_block(validator)
                if new_block:
                    logging.info(f"Successfully forged block #{new_block.index}")
                    # Broadcast the new block to peers
                    # Run broadcast in a separate thread to avoid blocking the forge loop?
                    # For simplicity, run sequentially for now.
                    blockchain.broadcast_block(new_block)
                else:
                     logging.warning("Block forging failed (e.g., create_new_block returned None).")

            elif validator:
                logging.info(f"Node {node_identifier} was not selected (validator is {validator}). Waiting.")
            else:
                 logging.warning("No validator could be selected (e.g., no stakes).")

        except Exception as e:
             logging.error(f"Error in forging loop: {e}", exc_info=True) # Log traceback
             # Avoid tight loop on error
             sleep_duration = max(sleep_duration, 60) # Wait longer if error occurs

        logging.debug(f"Forge loop sleeping for {sleep_duration} seconds...")
        sleep(sleep_duration)


# --- Main Execution ---
if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Run a Proof-of-Stake Blockchain Node with Wallets/Tokens.')
    parser.add_argument('-p', '--port', default=5000, type=int, help='Port to listen on.')
    parser.add_argument('--host', default='0.0.0.0', help='Host to bind to (0.0.0.0 allows external connections).')
    parser.add_argument('--peers', default=None, type=str, help='Comma-separated list of initial peer node addresses (e.g., 127.0.0.1:5001,127.0.0.1:5002)')
    # Use port as part of the identifier for local testing
    parser.add_argument('--id', default=None, type=str, help='Unique identifier for this node (for PoS staking, defaults to 127.0.0.1:port)')

    args = parser.parse_args()
    port = args.port
    host = args.host

    # Set node identifier (used for PoS staking)
    node_identifier = args.id if args.id else f"127.0.0.1:{port}" # Default to localhost:port for staking ID

    # Define data file path based on port for local testing uniqueness
    data_file = os.path.join(DATA_DIR, f"node_{port}_data.json") # Changed filename slightly

    # Initialize blockchain
    blockchain = Blockchain(node_identifier=node_identifier, data_file=data_file)
    logging.info(f"Node identifier (for PoS): {node_identifier}")
    logging.info(f"Token Name: {TOKEN_NAME}")
    logging.info(f"Data file: {data_file}")


    # Register initial peers from command line
    if args.peers:
        initial_peers = args.peers.split(',')
        logging.info(f"Registering initial peers: {initial_peers}")
        for peer in initial_peers:
             blockchain.register_node(peer.strip()) # Register function handles parsing/scheme

    # Start background thread for forging
    forge_thread = threading.Thread(target=forging_loop, daemon=True)
    forge_thread.start()
    logging.info("Background forging loop started.")

    # Start Flask server
    logging.info(f"Starting node API server on {host}:{port}")
    # Disable Flask's default logger if using basicConfig to avoid duplicate logs
    log = logging.getLogger('werkzeug')
    log.setLevel(logging.WARNING)
    app.run(host=host, port=port)


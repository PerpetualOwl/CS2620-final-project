# 4/15/25
Blockchain project init.
- Define Block structure:
    - index
    - timestamp
    - transactions (list, JSON format)
    - previous_hash
    - hash (self)
- Basic Python project setup:
    - venv
    - requirements.txt

# 4/17/25
Block class done. Chain implementation next.
- Chain: Python list.
- Genesis block: Need creation function. `create_genesis_block()`.
- New blocks: `add_block()` function. Link via `previous_hash`.
- Hashing: `hashlib.sha256`. Standard choice.

# 4/20/25
Need mining difficulty. Proof-of-Work (PoW).
- Problem: Anyone can add blocks instantly.
- Solution: Require computational work.
- PoW concept: Find `nonce` such that `hash(index + timestamp + transactions + previous_hash + nonce)` has N leading zeros.
- Difficulty parameter: N (e.g., 4). Controls mining time.
- Need `proof_of_work(last_proof)` function.

# 4/22/25
PoW implemented.
- `proof_of_work` function:
    - Takes previous proof/hash.
    - Iterates nonce until valid hash found.
- Block class updated: Added `nonce` field.
- Tested: Finding nonce takes time. Difficulty scaling works.
- Integration: Call PoW before adding block in `add_block`.

# 4/24/25
API design phase. Flask selected.
- Key endpoints:
    - `GET /chain`: Fetch entire blockchain.
    - `POST /transactions/new`: Add transaction to pending pool.
    - `GET /mine`: Trigger mining process.
- OpenAPI spec (`blockchain_openapi.yaml`) started. Documenting API structure.

# 4/26/25
Flask app (`blockchain_node.py`) coding started.
- `GET /chain`: Implemented. Returns `self.chain`.
- `POST /transactions/new`: Implemented.
    - Takes JSON payload.
    - Appends to `self.pending_transactions`.
- Note: No transaction validation yet. Add later.

# 4/28/25
`GET /mine` endpoint implemented.
- Mining process:
    1. Get last block: `last_block = self.chain[-1]`
    2. Get last proof: `last_proof = last_block['proof']`
    3. Calculate new proof: `proof = self.proof_of_work(last_proof)`
    4. Add miner reward transaction.
    5. Create new block: `new_block = self.create_block(proof, previous_hash)` (using pending txns)
    6. Append to chain: `self.chain.append(new_block)`
- Unit tests started:
    - `tests/test_block.py`
    - `tests/test_blockchain_unit.py` (Focus on core logic)

# 4/29/25
API tests (`tests/test_api.py`) written.
- Using `requests` against local Flask instance.
- Test cases:
    - `/chain` returns list.
    - `/transactions/new` accepts POST, increases pending count.
    - `/mine` creates a new block, increases chain length.
- Basic functionality confirmed.
- Next major task: Decentralization. Networking (P2P), Consensus algorithm.
- Initial consensus: Longest chain wins. Simple, defer complex logic.

# 4/30/25
Shift focus: Exchange functionality.
- Need a way for users to trade assets represented on the blockchain.
- Basic concept: Centralized order book managed by an exchange server.
- `exchange.py`: Define `Order` class (user, asset, amount, price, type: buy/sell).
- `exchange_server.py`: Flask app for the exchange.
- API endpoints needed:
    - `POST /orders/new`: Submit a new buy/sell order.
    - `GET /orders`: View open orders for an asset.
    - `GET /trades`: View completed trades for an asset.

# 5/2/25
Exchange server implementation progress.
- `exchange.py`: Added `OrderBook` class.
    - Stores buy/sell orders.
    - Matching logic: `match_orders()`. Simple price-time priority for now.
- `exchange_server.py`:
    - Implemented `POST /orders/new`. Adds order to the `OrderBook`. Calls `match_orders`.
    - Implemented `GET /orders`. Returns current state of the order book.
    - Implemented `GET /trades`. Returns list of matched trades.
- Need persistence. Storing orders/trades in memory only for now.

# 5/4/25
Testing the exchange.
- Wrote `tests/test_exchange.py` (assuming this file exists or should be created conceptually for the notebook).
    - Unit tests for `Order` and `OrderBook` classes.
    - Test order matching logic (various scenarios: full match, partial match, no match).
- API tests for `exchange_server.py`:
    - Use `requests` similar to `test_api.py`.
    - Test submitting orders, checking order book, verifying trades.
- Integration thoughts: How does the exchange interact with the blockchain node?
    - Need to verify user balances (on-chain) before accepting orders.
    - Need to settle completed trades by creating blockchain transactions. Future work.




# Overall discussion


## What our project does
The core motivation behind this project was to gain hands-on experience with fundamental blockchain concepts and explore how digital assets could be managed and traded within a custom-built ecosystem. We aimed to move beyond theoretical understanding and tackle the practical challenges of implementing core components like block creation, hashing, proof-of-work consensus, and transaction handling. By building from the ground up, we could better appreciate the design decisions and trade-offs involved in creating a distributed ledger system, even a simplified one. The goal wasn't necessarily to create a production-ready system, but rather a functional prototype that demonstrates these key principles in action and serves as a learning platform.

Our project implements a foundational blockchain network using Python. This network forms an immutable, append-only ledger where transactions are grouped into blocks and cryptographically linked together using SHA-256 hashes. Each block contains a timestamp, a list of transactions, its own hash, and the hash of the preceding block, creating a verifiable chain of history. We implemented a Proof-of-Work (PoW) consensus mechanism to regulate the creation of new blocks. Miners must solve a computational puzzle (finding a nonce that results in a hash with a specific number of leading zeros) to validate a block of transactions and add it to the chain, receiving a reward in the process. This PoW system secures the network against trivial block additions and introduces a controlled rate of block creation.

Built upon this blockchain infrastructure, we introduced two distinct digital assets, let's call them TokenA (TKA) and TokenB (TKB), represented within the transaction data. These tokens exist purely on our custom blockchain, and their ownership and transfer are recorded immutably within the ledger. Users can initiate transactions to send TKA or TKB to other users, and these transactions are bundled into blocks by miners. The blockchain thus serves as the definitive record keeper for the balances and movement of these two native tokens, providing a transparent and tamper-resistant history of all token activity within our system.

To facilitate the trading of these native tokens (TKA and TKB), we developed a separate, centralized exchange server, also built with Python and Flask. This exchange provides a platform for users to place buy and sell orders for TKA against TKB, and vice-versa. It features an order book mechanism that matches compatible buy and sell orders based on price-time priority. Users interact with the exchange via a simple API to submit orders, view the current order book, and see a history of completed trades. While currently centralized and operating off-chain for matching, the long-term vision involves integrating it more tightly with the blockchain for balance verification and trade settlement, bridging the gap between the off-chain matching engine and the on-chain ledger.

In essence, the project combines a custom-built Proof-of-Work blockchain, acting as the secure ledger for two native digital tokens, with a centralized exchange service that enables users to trade these tokens. It provides APIs for interacting with both the blockchain node (mining, sending transactions, viewing the chain) and the exchange server (placing orders, viewing market data). This setup allows us to explore both the core mechanics of blockchain technology and the application layer services, like exchanges, that can be built on top of such systems.


## How our project does it
The entire project, encompassing both the blockchain node and the exchange server, is implemented exclusively in Python 3, leveraging standard libraries and a few common external packages managed via `requirements.txt`. We utilized Flask, a lightweight web framework, to build the API servers for both the blockchain node (`blockchain_node.py`) and the exchange (`exchange_server.py`), enabling interaction via standard HTTP requests. Data serialization and communication between components and potential clients rely on JSON payloads, ensuring language-agnostic interoperability.

The blockchain core logic resides primarily within the `Blockchain` class in `blockchain_node.py`. The chain itself is stored in memory as a Python list of dictionaries, where each dictionary represents a block. A block contains standard fields: `index`, `timestamp` (generated using `time.time()`), `transactions` (a list of transaction dictionaries), `proof` (the nonce found during mining), and `previous_hash`. Block integrity and linkage are maintained using SHA-256 hashing provided by Python's `hashlib` module. The `hash` method within the `Blockchain` class calculates the hash of a block by first creating a sorted JSON string representation of the block dictionary to ensure consistent hashing.

Proof-of-Work consensus is implemented in the `proof_of_work` method. It takes the previous block's proof as input and iteratively checks nonce values (starting from 0) until a hash is found that satisfies the difficulty criteria (a predefined number of leading zeros). The `valid_proof` helper method checks this condition. Transactions are simple dictionaries containing `sender`, `recipient`, `amount`, and `token_type` (e.g., 'TKA' or 'TKB'). New transactions submitted via the `/transactions/new` API endpoint are temporarily stored in a `pending_transactions` list before being included in the next block during the mining process triggered by the `/mine` endpoint.

The exchange functionality is separated into `exchange.py` (core logic) and `exchange_server.py` (API layer). `exchange.py` defines an `Order` class (using simple attributes or potentially `dataclasses`) and an `OrderBook` class. The `OrderBook` maintains separate lists for buy and sell orders for different trading pairs (e.g., TKA/TKB). The core matching logic resides in the `match_orders` method within `OrderBook`, which implements a basic price-time priority algorithm: it attempts to match the highest bid with the lowest ask, executing trades if prices overlap and recording them. The `exchange_server.py` uses Flask to expose endpoints like `/orders/new` (which adds an order to the `OrderBook` and triggers matching), `/orders` (to view open orders), and `/trades` (to view completed trades). Currently, the order book and trade history reside in memory.

An OpenAPI specification (`blockchain_openapi.yaml`) formally defines the RESTful APIs for both the blockchain node and the exchange server. This specification details the available endpoints, expected request methods (GET/POST), request body schemas (JSON), and response schemas (JSON). This serves as documentation and could potentially be used with tools to generate client code or perform API validation. Testing is handled using `pytest` for unit tests (`tests/test_block.py`, `tests/test_blockchain_unit.py`, `tests/test_exchange.py`) covering the core classes and logic, and Python's `requests` library for integration/API tests (`tests/test_api.py`) that interact with the running Flask servers.

## What we learned while building it
Building this project provided significant practical learning beyond just blockchain theory. Debugging the Proof-of-Work implementation, even in its basic form, highlighted the challenges inherent in consensus mechanisms; ensuring blocks hash correctly and proofs validate consistently required careful attention to detail and systematic testing. We also gained valuable experience in managing parallel development streams, working simultaneously on the core blockchain node and the separate exchange server. This necessitated clear communication and interface definition between the two components.

Defining the APIs using the OpenAPI specification (`blockchain_openapi.yaml`) proved incredibly useful. It forced us to think clearly about how the blockchain node and exchange server would interact, serving as a contract between the components even before full implementation. This made integration smoother and provided clear documentation. We also learned the practicalities of building and testing simple RESTful APIs using Python and Flask, understanding request handling, JSON serialization, and the importance of both unit tests (using `pytest`) for core logic and integration tests (using `requests`) for API endpoints. Overall, it was a practical introduction to building multi-component systems and the tools needed to manage their complexity.

# presentation link:

https://docs.google.com/presentation/d/1psz_UfMuVr__0O4LnneaEMYbQ6uc53p09YmRWcVGqo0/edit#slide=id.p3
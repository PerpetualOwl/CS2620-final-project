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
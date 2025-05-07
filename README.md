# Proof-of-Stake Blockchain Simulation (Dual Token)

This project simulates a simple Proof-of-Stake (PoS) blockchain network using Python and Flask. It features multiple nodes that can communicate, forge blocks, validate transactions for two different tokens (MAIN and SECOND), and reach consensus using the longest valid chain rule. It also includes a basic web UI for interaction and an OpenAPI specification for the API. An optional exchange server component is also included.

## Features

*   **Proof-of-Stake Consensus:** Nodes are selected to forge blocks based on their stake (simulated).
*   **Multiple Nodes:** Run several nodes concurrently that discover and communicate with each other.
*   **Dual Token Support:** Handles transactions for two distinct tokens ("MAIN" and "SECOND").
*   **Transaction Validation:** Basic validation of transactions, including sender balance checks (except for the faucet address '0').
*   **Wallet Simulation:** Create simple UUID-based wallet addresses and check balances.
*   **Faucet Address:** Use address '0' to mint new tokens for testing.
*   **Persistence:** Node state (chain, stakes, known wallets) is saved to disk (`data/node_xxxx_data.json`).
*   **Web UI:** A simple Flask-based web interface (`/`) to view the chain, pending transactions, nodes, wallets, send transactions, and trigger consensus.
*   **REST API:** A defined API (see `blockchain_openapi.yaml`) for programmatic interaction.
*   **Makefile:** Simplifies installation, running nodes, testing, and cleanup.
*   **Exchange Server (Optional):** A separate server (`exchange_server.py`) for potential future exchange functionality.

## Installation

1.  **Clone the repository (if you haven't already):**
    ```bash
    git clone <your-repo-url>
    cd <repository-directory>
    ```

2.  **Ensure you have Python 3 installed.**

3.  **Install dependencies:**
    The `Makefile` provides a convenient target to install both runtime and development dependencies.
    ```bash
    make install_dev
    ```
    This command installs packages listed in `requirements.txt` and `requirements-dev.txt` using pip.

## Running the Blockchain Nodes

The `Makefile` simplifies running a multi-node network locally.

*   **Run a 3-node network (Ports 10000, 10001, 10002):**
    ```bash
    make run_nodes
    ```
    This starts three nodes in the background. Each node is automatically configured to know about the other two.

*   **Run a specific node (e.g., Port 10000):**
    ```bash
    make run_node_10000
    ```
    (Similar targets exist: `run_node_10001`, `run_node_10002`)
    This runs the node in the foreground, which can be useful for debugging.

*   **Accessing the UI:**
    Once a node is running, you can access its web UI in your browser:
    *   Node 1: `http://127.0.0.1:10000`
    *   Node 2: `http://127.0.0.1:10001`
    *   Node 3: `http://127.0.0.1:10002`

## Running the Exchange Server (Optional)

*   **Start the exchange server (Port 8000):**
    ```bash
    make run_exchange
    ```
    This runs the `exchange_server.py` script.

## Running Tests

*   **Execute the test suite:**
    ```bash
    make test
    ```
    This first ensures dependencies are installed (`make install_dev`) and then runs the tests located in the `tests/` directory using `pytest`.

## Stopping Services

*   **Stop all running blockchain nodes:**
    ```bash
    make stop_nodes
    ```
    *Note: This uses `pkill` based on the script name (`blockchain_node.py`). Be cautious if you have other unrelated Python processes running the same script.*

*   **Stop the exchange server:**
    ```bash
    make stop_exchange
    ```
    *Note: This also uses `pkill` based on the script name (`exchange_server.py`).*

## Cleaning Up

*   **Stop nodes and remove the data directory:**
    ```bash
    make clean
    ```
    This first runs `make stop_nodes` and then removes the `data/` directory where node states are stored.

## API Overview

The blockchain nodes expose a REST API documented in `blockchain_openapi.yaml`. Key endpoints include:

*   `GET /`: Serves the HTML UI.
*   `POST /transactions/new`: Submit a new transaction.
*   `GET /chain`: Retrieve the node's full blockchain.
*   `POST /nodes/register`: Register peer nodes.
*   `GET /nodes/get`: Get the list of known peers.
*   `GET /resolve`: Trigger the consensus mechanism.
*   `POST /receive_block`: Endpoint for peers to send newly forged blocks.
*   `POST /wallet/new`: Create a new wallet address.
*   `GET /balance/{address}`: Get the balance for a specific address.

Refer to `blockchain_openapi.yaml` for detailed request/response schemas.
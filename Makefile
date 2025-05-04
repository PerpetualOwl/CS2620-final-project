# Makefile for running Proof-of-Stake Blockchain Nodes

# Default Python interpreter
PYTHON = python3

# Base script name
SCRIPT = blockchain_node.py

# Directory for node data
DATA_DIR = data

# Ports for the nodes
PORTS = 10000 10001 10002

# --- Targets ---

.PHONY: all clean run_nodes stop_nodes run_node_10000 run_node_10001 run_node_10002 test install_dev

# Default target: runs multiple nodes
all: run_nodes

# Clean up data directory and potentially running processes
clean: stop_nodes
	@echo "Removing data directory..."
	@rm -rf $(DATA_DIR)
	@echo "Cleanup complete."

# Run multiple nodes in the background
run_nodes:
	@echo "Starting multiple blockchain nodes..."
	@mkdir -p $(DATA_DIR) # Ensure data directory exists
	# Start node 1 (port 10000), knowing about 10001, 10002
	@echo "Starting node on port 10000..."
	@$(PYTHON) $(SCRIPT) --port 10000 --peers 127.0.0.1:10001,127.0.0.1:10002 &
	# Start node 2 (port 10001), knowing about 10000, 10002
	@echo "Starting node on port 10001..."
	@$(PYTHON) $(SCRIPT) --port 10001 --peers 127.0.0.1:10000,127.0.0.1:10002 &
	# Start node 3 (port 10002), knowing about 10000, 10001
	@echo "Starting node on port 10002..."
	@$(PYTHON) $(SCRIPT) --port 10002 --peers 127.0.0.1:10000,127.0.0.1:10001 &
	@echo "Nodes started in background. Check logs or access http://127.0.0.1:[port]"

# Stop nodes (simple version using pkill - adjust if needed)
# WARNING: This is aggressive and might kill other Python processes
# using the same script name if not careful.
stop_nodes:
	@echo "Attempting to stop running blockchain nodes..."
	@-pkill -f "$(PYTHON) $(SCRIPT)" || echo "No running nodes found or pkill failed."
	@echo "Stop command executed."

# Individual targets to run specific nodes (useful for debugging)
run_node_10000:
	@mkdir -p $(DATA_DIR)
	$(PYTHON) $(SCRIPT) --port 10000 --peers 127.0.0.1:10001,127.0.0.1:10002

run_node_10001:
	@mkdir -p $(DATA_DIR)
	$(PYTHON) $(SCRIPT) --port 10001 --peers 127.0.0.1:10000,127.0.0.1:10002

run_node_10002:
	@mkdir -p $(DATA_DIR)
	$(PYTHON) $(SCRIPT) --port 10002 --peers 127.0.0.1:10000,127.0.0.1:10001


# Install development dependencies
install_dev:
	@echo "Installing development requirements..."
	@$(PYTHON) -m pip install -r requirements.txt
	@$(PYTHON) -m pip install -r requirements-dev.txt

# Run tests using pytest
test: install_dev
	@echo "Running tests..."
	@$(PYTHON) -m pytest -v tests/
	@echo "Tests finished."

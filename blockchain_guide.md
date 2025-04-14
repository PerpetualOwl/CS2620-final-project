# **User Guide: Interacting with the SIMCOIN Blockchain Simulation**

This guide explains how to use the web interface to interact with the simulated Proof-of-Stake blockchain. You can create wallets, get initial tokens from a "faucet", transfer tokens between wallets, and observe the blockchain.

## **Prerequisites**

* You need to have the blockchain nodes running. You can usually start multiple nodes using the provided Makefile by running make run\_nodes in your terminal in the directory containing blockchain\_node.py and Makefile.

## **Step 1: Accessing the Node UI**

1. Open your web browser.  
2. Navigate to the address of one of the running nodes. If you used `make run\_nodes`, you can typically access them at:  
   * http://127.0.0.1:10000  
   * http://127.0.0.1:10001  
   * http://127.0.0.1:10002  
3. You should see the web interface for that specific blockchain node.

## **Step 2: Creating a Wallet**

1. Find the **Wallets & Balances** section on the page.  
2. Under "Create New Wallet", click the **Create Wallet** button.  
3. A message will appear at the top confirming "Wallet created: \[your-new-wallet-address\]".  
4. The new address will also appear in the "Known Wallet Addresses" list.  
5. **Copy this new wallet address.** You'll need it for sending and receiving tokens. Remember, there's no private key to manage in this simulation – the address is all you have.

## **Step 3: Obtaining Initial Tokens (Using the Faucet)**

To get started, you need some SIMCOIN. We use a special "faucet" address 0 that can create tokens.

1. Go to the **Send SIMCOIN Transaction** section.  
2. In the **Sender Address** field, enter exactly: 0  
3. In the **Recipient Address** field, paste the **wallet address you created** in Step 2\.  
4. In the **Amount (SIMCOIN)** field, enter the number of tokens you want (e.g., 1000).  
5. Click the **Submit Transaction** button.  
6. You should see a confirmation message at the top, and the transaction will appear in the **Pending Transactions** list lower down the page.

## **Step 4: Waiting for Confirmation**

Transactions in the "Pending" list aren't yet part of the blockchain. They need to be included in a new block.

1. The nodes automatically try to "forge" (create) new blocks containing pending transactions every 20 seconds (based on the FORGING\_INTERVAL\_SECONDS setting).  
2. One node (chosen based on stake) will create the block and broadcast it to the others.  
3. Wait about 20-30 seconds.  
4. Refresh the page (Ctrl+R or Cmd+R). The transaction should disappear from the "Pending Transactions" list and appear inside the latest block shown at the bottom under the "Blockchain" section.

## **Step 5: Checking Your Balance**

Now that the transaction is confirmed in a block, you can check your wallet's balance.

1. Go to the **Wallets & Balances** section.  
2. Under "Check Balance", paste your **wallet address** into the "Wallet Address" field.  
3. Click the **Get Balance** button.  
4. The page will refresh, and an alert box should appear under the "Check Balance" form showing the balance for your address (e.g., "Balance for \[your-address\]: **1000 SIMCOIN**").

## **Step 6: Trading Tokens**

Let's simulate sending tokens from one wallet to another.

1. **Create a second wallet address** using the method in Step 2\. Copy this second address.  
2. Go to the **Send SIMCOIN Transaction** section.  
3. In the **Sender Address** field, paste the address of your **first wallet** (the one that received tokens from the faucet).  
4. In the **Recipient Address** field, paste the address of your **second wallet**.  
5. In the **Amount (SIMCOIN)** field, enter an amount **less than or equal to** the balance of your first wallet (e.g., 250).  
6. Click **Submit Transaction**.  
7. Wait for the transaction to be confirmed in a block (Step 4).  
8. Check the balances of **both** wallets (Step 5). You should see the first wallet's balance decreased and the second wallet's balance increased by the amount you transferred. If you try to send more than you have, the transaction will fail (check the flash message and logs).

## **Other Features**

* **Register Peer Nodes:** Allows you to manually tell a node about other nodes on the network. The Makefile usually handles initial connections.  
* **Resolve Conflicts:** Manually triggers the consensus mechanism. If this node's chain is shorter than a valid chain found on another peer, it will adopt the longer chain.

You can now experiment with creating more wallets, sending transactions between them, and observing how the blockchain state is updated across the different nodes (by accessing their individual UIs).
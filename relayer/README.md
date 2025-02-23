# Relayer

A relayer connects two blockchains

Connects to blockchains through connectors

Two processes: synchronize trust roots, monitor and forward cross-chain transactions

## Process 1: Monitor Latest Blocks

Monitor the latest blocks of the blockchain
- Put block headers into `headerQueue`
- Filter cross-chain transactions and put them into `xtxQueue`

## Process 2: Forward Transactions

### Sub-process 2.1: Forward Block Header Transactions

- Monitor `headerQueue`
- Build target chain transaction `target_tx`
- Forward `target_tx` to target chain

### Sub-process 2.2: Forward Cross-chain Transactions

- Monitor `xtxQueue`
- Build transaction proof
- Build target chain transaction `target_tx`
- Forward `target_tx` to target chain

## Connector

### Query Latest Block

def query_latest_block() -> Block:

### Query Transaction Proof

def query_xtx_proof(tx: Transaction) -> str:

### Query Transaction Receipt Proof

def query_xtx_receipt_proof(self, xtx: Transaction) -> str:

### Build Transaction

def build_xtx() -> Transaction:

### Forward Transaction

def send_tx(ctx: Transaction)


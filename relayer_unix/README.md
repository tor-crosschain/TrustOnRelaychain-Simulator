# Relayer

A relayer connects two blockchains

Connects blockchains through a connector

Two processes: synchronize trust roots, listen and forward cross-chain transactions

## Process 1: Listen to the latest block

Listen to the latest block of the blockchain
- Put the block header into `headerQueue`
- Filter cross-chain transactions into `xtxQueue`

## Process 2: Forward transactions

### Subprocess 2.1: Forward block header transactions

- Listen to `headerQueue`
- Construct target chain transaction `target_tx`
- Forward `target_tx` to the target chain

### Subprocess 2.2: Forward cross-chain transactions

- Listen to `xtxQueue`
- Construct transaction proof
- Construct target chain transaction `target_tx`
- Forward `target_tx` to the target chain

## Connector

### Query the latest block

def query_latest_block() -> Block:

### Query transaction proof

def query_xtx_proof(tx: Transaction) -> str:

### Query transaction receipt proof

def query_xtx_receipt_proof(self, xtx: Transaction) -> str:

### Build transaction

def build_xtx() -> Transaction:

### Send transaction

def send_tx(ctx: Transaction)


# Data Structures

## Block

|Field|Description|
|-|-|
|A|B|

## Transaction
<!-- # basic property
self.sender: str = sender
self.to: str = to
self.data: str = data
self.memo: str = memo

# dynamic property, changing with consensus
self.height: int = height
self.status: TxStatus = status -->
|Field      |Type      |Description|
|---        |---       |---        |
|sender     |str       |Sender     |
|to         |str       |Receiver, all are contract identifiers|
|data       |str(json) |Transaction data, contract function and parameters to be executed|
|memo       |str(json) |Memo, usually specifies transaction type, such as cross-chain transaction type|

**to**
The data type of 'to' is str.

When 'to' is empty `''`, the transaction type is deployment;

When 'to' is not empty, the transaction type is execution;
- When `to = 'base'`, the transaction executes storage operations;
- When `to = '{hexstr}'`, the transaction executes a specific contract;

**data**
The data type of 'data' is str, with two forms:
```python
# Form 1: execute contract
# str(json)
data = json.dumps({
    'func': '',
    'arguments': [],
})

# Form 2: deploy a contract
# str
code_add = CodeAdd()
ctr = pickle.dumps(code_add).hex() # Convert to hexadecimal string
data = ctr
```

**memo structure**
The data type of 'memo' is str(json), i.e., a JSON format string.
```python
memo = json.dumps({
    'type': '',
    'info': {},
})
```
|type: str|info: json|Description|
|---|---|---|
|CTX-SRC|```{'dst': 2, 'other_key': 'other_val'}```|Source chain transaction|
|CTX-DST|```{'src': 1, 'other_key': 'other_val'}```|Destination chain transaction|
|CTX-HEADER|```{'src': 1, 'height': 100, 'other_key': 'other_val'}```|Block header transaction|
|''(empty `type`)|```{'other_key': 'other_val'}```|Normal transaction|

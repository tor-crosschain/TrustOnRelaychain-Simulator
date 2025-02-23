## VM Description

## Executor

`Executor`, external calls to `execute_tx` to execute transactions.

## Contracts

`CodeMeta`, each contract must implement the methods of `CodeMeta`.

Each contract is stored in the database in the form of `pickle.dumps(source_code)`. All persistent data involved in the contract is stored in `store`.

`CodeMeta` accepts a storage `store`, contracts can directly use this storage to store content. `Executor` assigns this storage before each contract call.

The built-in contract name is `base`, which can concisely handle basic storage operations for testing purposes.

## Storage

There is only 1 global `store`, which is passed to the `Executor` when executing transactions for each block.

Both `key` and `value` in each `store` are of type `str`.
import json
import time
import queue
import asyncio
from asyncio.queues import QueueEmpty as QueueEmptyException

# from queue import Empty as QueueEmptyException
from chain_simulator.types.transaction import Transaction, TxStatus
from typing import Any, Union, List


def mark_tx(key: str, tx: Transaction) -> Transaction:
    mp_put_time = time.time()
    memo: dict = json.loads(tx.memo)
    ts = memo.get("ts", {})
    mp_put: List = ts.get(key, []) 
    assert isinstance(mp_put, List)
    mp_put.append(mp_put_time)
    ts[key] = mp_put
    memo["ts"] = ts
    tx.memo = json.dumps(memo)
    return tx


class SyncMemPool(queue.Queue):
    def __init__(self, maxsize: int = 0) -> None:
        super().__init__(maxsize)

    def put_tx(self, newtx: Transaction) -> bool:
        if self.qsize() >= self.maxsize and self.maxsize > 0:
            print(f"qsize: {self.qsize()}, maxsize: {self.maxsize}")
            return False
        newtx = mark_tx(key="mp_put", tx=newtx)
        newtx.status = TxStatus.PENDING
        self.put(newtx)
        return True

    def pop_tx(self) -> Union[Transaction, None]:
        tx: Transaction = None
        try:
            tx = self.get_nowait()
            tx = mark_tx(key="mp_get", tx=tx)
        except QueueEmptyException:
            pass
        finally:
            return tx

    def size(self) -> int:
        return self.qsize()


class AsyncMemPool(asyncio.Queue):
    def __init__(self, maxsize: int = 0) -> None:
        super().__init__(maxsize)

    async def put_tx(self, newtx: Transaction) -> bool:
        if self.qsize() >= self.maxsize and self.maxsize > 0:
            print(f"qsize: {self.qsize()}, maxsize: {self.maxsize}")
            return False
        newtx = mark_tx(key="mp_put", tx=newtx)
        newtx.status = TxStatus.PENDING
        await self.put(newtx)
        return True

    async def pop_tx(self) -> Union[Transaction, None]:
        tx: Transaction = None
        try:
            tx = self.get_nowait()
            tx = mark_tx(key="mp_get", tx=tx)
        except QueueEmptyException:
            pass
        finally:
            return tx

    def size(self) -> int:
        return self.qsize()

"""
blockchain simulator core:
1. replace consensus with time intervals
2. simulate tx pool and block generation
"""

import time
import asyncio
import pickle
import traceback
import json

from typing import List, Optional, Union
from chain_simulator.mempool import mempool
from chain_simulator.types.transaction import (
    Transaction,
    TxStatus,
    TransactionIndexer,
)
from chain_simulator.blockchain.context import Context
from chain_simulator.types.block import Block
from chain_simulator.config.config import Config
from chain_simulator.vm.executor import Executor
from chain_simulator.vm.store import BaseStore
from chain_simulator.vm.base.CtrBase import CtrBase
from chain_simulator.vm.base.CtrLightClient import CtrLightClient


class Blockchain(object):
    def __init__(self, pool: mempool.AsyncMemPool, config: Config) -> None:
        self.blocks: List[Block] = []
        self.blocks.append(self.__genesis_block())
        self.txpool = pool
        self.config = config
        self.store = BaseStore()
        self.ctx = Context()
        self.txindexer = TransactionIndexer()
        self.stopped = False
        self.mining = True
        self.execute_realtime = 0
        self.__pre_store()

    def __pre_store(self) -> None:
        # store contract: base
        _base = CtrBase()
        data = pickle.dumps(_base).hex()
        executor = Executor(self.ctx, self.store)
        resp = executor.deploy(0, 0, data, name="base") 
        assert resp.code == 1, f"pre deploy failed! code={resp.code}, out={resp.out}"
        assert resp.out == "base", f"pre deploy out must be 'base'! out={resp.out}"

        # store contract: lightclient
        _lightclient = CtrLightClient()
        data = pickle.dumps(_lightclient).hex()
        executor = Executor(self.ctx, self.store)
        resp = executor.deploy(
            0, 0, data, name="lightclient"
        )  
        assert resp.code == 1, f"pre deploy failed! code={resp.code}, out={resp.out}"
        assert (
            resp.out == "lightclient"
        ), f"pre deploy out must be 'lightclient'! out={resp.out}"

    def __genesis_block(self) -> Block:
        block = Block()
        block.timestamp = time.time()
        block.height = 0
        return block

    def select_txs_from_pool(self) -> List[Transaction]:
        txs: List[Transaction] = []
        while True:
            tx = self.txpool.pop_tx()
            if tx is None:
                break
            txs.append(tx)
            tx.status = TxStatus.PROPOSING
            if len(txs) == self.config.block_size:
                break
        return txs

    def propose_block(self) -> None:
        block = Block()
        block.timestamp = time.time()
        txs = self.select_txs_from_pool()
        block.txs = txs
        block.height = len(self.blocks)
        self.ctx.set(block=block)

    async def propose_block_and_exec(self) -> None:
        block = Block()
        block.timestamp = time.time()
        block.height = len(self.blocks)
        self.ctx.set(block=block)
        cnt_tx = 0
        exec = Executor(self.ctx, self.store)
        starttime = time.perf_counter_ns()
        endtime = starttime
        txs: List[Transaction] = []
        while True:
            tx = await self.txpool.pop_tx()
            if tx is None:
                break
            tx.status = TxStatus.PROPOSING
            resp = await exec.execute_tx(block.height, cnt_tx, tx)
            tx.status = TxStatus.SUCCESS if resp.code == 1 else TxStatus.FAILED
            tx.out = resp.out
            txs.append(tx)
            cnt_tx += 1
            endtime = time.perf_counter_ns()
            interval = endtime - starttime
            if interval >= self.config.execute_timeout_ns:
                print(f"interval: {interval}")
                break
            if cnt_tx == self.config.block_size:
                break
        self.execute_realtime = (endtime - starttime) / (10**9)
       
        block.txs = txs
        self.ctx.set(block=block)

    async def execute(self) -> None:
        exec = Executor(self.ctx, self.store)
        for idx, tx in enumerate(self.ctx.block.txs):
            resp = await exec.execute_tx(self.ctx.block.height, idx, tx)
            self.ctx.block.txs[idx].status = (
                TxStatus.SUCCESS if resp.code == 1 else TxStatus.FAILED
            )
            self.ctx.block.txs[idx].out = resp.out

    async def consensus(self) -> None:
        """
        use fixed time interval to replace the consensus process
        use asynic.sleep() to sleep because time.sleep() blocks the coroutine then other coroutines cannot get the chance to run
        """
        rest = self.config.block_interval - (self.execute_realtime)
        rest = 0.01 if rest < 0 else rest
        await asyncio.sleep(rest)

    def commit(self) -> None:

        def mark_tx():
            # mark the commit time of the transaction
            commit_time = time.time()
            for idx in range(len(self.ctx.block.txs)):
                memo: dict = json.loads(self.ctx.block.txs[idx].memo)
                ts = memo.get("ts", {})
                commit: List = ts.get("commit", []) 
                assert isinstance(commit, List)
                commit.append(commit_time)
                ts["commit"] = commit
                memo["ts"] = ts
                self.ctx.block.txs[idx].memo = json.dumps(memo)

        def index_tx():
            for tx in self.ctx.block.txs:
                self.txindexer.store(tx)

        def update_tx():
            for tx in self.ctx.block.txs:
                tx.height = self.ctx.block.height
                tx.status = TxStatus.SUCCESS

        self.blocks.append(self.ctx.block)
        mark_tx()
        index_tx()
        update_tx()
        print(
            f"{time.time():.2f}, commit block({self.ctx.block.height}), num_txs={len(self.ctx.block.txs)}"
        )
        self.ctx.reset()

    @property
    def block_num(self) -> int:
        return len(self.blocks) - 1

    def get_block_by_height(self, height: int) -> Optional[Block]:
        if height >= len(self.blocks):
            return None
        return self.blocks[height]

    def get_tx_proof(self, txhash: Union[bytes, str]) -> Optional[bytes]:
        if isinstance(txhash, str):
            txhash = bytes.fromhex(txhash)
        return txhash 

    def get_tx_receipt_proof(self, txhash: Union[bytes, str]) -> bytes:
        if isinstance(txhash, str):
            txhash = bytes.fromhex(txhash)
        return txhash 

    def query_state(self, to: str, data: str) -> str:
        exec = Executor(self.ctx, self.store)
        resp = exec.query(to, data)
        return resp.to_str()

    async def start(self) -> None:
        print("blockchain start!")
        self.stopped = False
        while not self.stopped:
            if not self.mining:
                await asyncio.sleep(1)
                continue
            try:
                await self.propose_block_and_exec()
                await self.consensus()
                self.commit()
            except Exception as e:
                print("blockchain exeception: {}".format(traceback.format_exc()))
                break
            finally:
                pass
        print("blockchain stop!")

    def stop_mining(self) -> bool:
        print("stop mining")
        self.mining = False
        return True

    def start_mining(self) -> bool:
        self.mining = True
        return True

    def is_mining(self) -> bool:
        return self.mining

    def stop(self) -> None:
        print("stop blockchain")
        self.stopped = True

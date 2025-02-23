"""
base blockchain core
but:
1. use BlocksManager() store blocks
2. use StoresManger() store kvs
"""

import time
import asyncio
import pickle
import traceback
import json
import random
from typing import List, Optional, Union, Generator, Any
from chain_simulator.mempool import mempool
from chain_simulator.types.transaction import (
    Transaction,
    TranMemo,
    TxStatus,
    TransactionIndexer,
)
from chain_simulator.blockchain.context import Context
from chain_simulator.types.block import Block, BlockStorage
from chain_simulator.config.config import Config
from chain_simulator.vm.executor import Executor
from chain_simulator.vm.store import BaseStore
from chain_simulator.vm.base.CtrBase import CtrBase
from chain_simulator.vm.base.CtrLightClient import CtrLightClient


class BlockchainStates(object):
    def __init__(
        self,
        mp: mempool.SyncMemPool,
        blocks: BlockStorage,
        store: BaseStore,
        txindexer: TransactionIndexer,
        config: Config,
    ) -> None:
        self.mining = True
        self.stopped = False
        self.gen_xtx_flag = False  # Default not enabled
        self.a = 10
        self.txpool = mp
        self.blocks = blocks
        self.store = store
        self.txindexer = txindexer

    def stop_mining(self) -> None:
        self.mining = False
        self.a = 100

    def start_mining(self) -> None:
        self.mining = True
        self.a = 200

    def is_mining(self) -> bool:
        return self.mining

    def stop_bc(self) -> None:
        self.stopped = True

    def start_bc(self) -> None:
        self.stopped = False

    def is_running(self) -> bool:
        return not self.stopped

    def start_gen_xtx(self) -> bool:
        self.gen_xtx_flag = True
        return self.gen_xtx_flag

    def stop_gen_xtx(self) -> bool:
        self.gen_xtx_flag = False
        return self.gen_xtx_flag

    def is_genning_xtx(self) -> bool:
        return self.gen_xtx_flag

    def block_num(self) -> int:
        return self.blocks.block_num()

    def get_block_by_height(self, height: int) -> Optional[Block]:
        return self.blocks.get_block_by_height(height)

    def get_tx_proof(self, txhash: Union[bytes, str]) -> Optional[bytes]:
        if isinstance(txhash, str):
            txhash = bytes.fromhex(txhash)
        return txhash 

    def get_tx_receipt_proof(self, txhash: Union[bytes, str]) -> bytes:
        if isinstance(txhash, str):
            txhash = bytes.fromhex(txhash)
        return txhash  

    def query_state(self, to: str, data: str) -> str:
        exec = Executor(Context(), self.store)
        resp = exec.query(to, data)
        return resp.to_str()


class BlockchainMProc(object):
    def __init__(self, config: Config, bc_status_manager: BlockchainStates) -> None:
        self.blocks: BlockStorage = bc_status_manager.blocks
        self.blocks.append(self.__genesis_block().as_str())
        self.txpool = bc_status_manager.txpool
        self.config = config
        self.store = bc_status_manager.store
        self.ctx = Context()
        self.txindexer = bc_status_manager.txindexer
        self.stopped = False
        self.status_manager = bc_status_manager
        self.execute_realtime = 0
        self.__pre_store()

    def __pre_store(self) -> None:
        # store contract: base
        _base = CtrBase()
        data = pickle.dumps(_base).hex()
        executor = Executor(self.ctx, self.store)
        resp = executor.deploy(
            0, 0, data, name="base"
        )  
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

    def generate_xtx(self) -> Generator[Transaction, Any, Any]:
        def build_xtx(idx: int) -> Transaction:
            dstid = random.choice(self.config.xtx_config.dstids)
            chainclass = self.config.xtx_config.classes[dstid]
            srcid = self.config.xtx_config.srcid
            memo = {"type": TranMemo.CTXSRC, "dst": dstid}
            # source chain timestamp
            memo["ts"] = {"init": time.time()}
            info = {
                "sender": f"send/{srcid}/{self.blocks.block_num()}-{idx}",
                "to": "lightclient",
                "data": json.dumps(
                    {
                        "func": "app_init",
                        "arguments": [dstid, chainclass, "crosschain-data"],
                    }
                ),
                "memo": json.dumps(memo),
                "status": TxStatus.PROPOSING,
            }
            tx = Transaction.from_json(info)
            return tx

        for i in range(self.config.gen_xtx_num):
            tx = build_xtx(i)
            yield tx

    def select_txs_from_pool(self) -> List[Transaction]:
        txs: List[Transaction] = []

        # Whether to enable automatic generation of cross-chain transactions
        # print(f"is genning xtx: {self.status_manager.is_genning_xtx()}")
        if self.status_manager.is_genning_xtx():
            txs.extend(self.generate_xtx())

        if len(txs) >= self.config.block_size:
            return txs
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
        block.height = self.blocks.block_num() + 1
        self.ctx.set(block=block)

    async def propose_block_and_exec(self) -> None:
        block = Block()
        block.timestamp = time.time()
        block.height = self.blocks.block_num() + 1
        self.ctx.set(block=block)
        cnt_tx = 0
        exec = Executor(self.ctx, self.store)
        starttime = time.perf_counter_ns()
        endtime = starttime
        txs: List[Transaction] = []
        while True:
            tx = self.txpool.pop_tx()
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
                # print(f"interval: {interval}")
                break
            if cnt_tx == self.config.block_size:
                break
        self.execute_realtime = (endtime - starttime) / (10**9)
        # print(f"execute realtime: {self.execute_realtime}")
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
        # rest = self.config.block_interval - (self.execute_realtime)
        # rest = 0.01 if rest < 0 else rest
        # await asyncio.sleep(rest)
        await asyncio.sleep(self.config.block_interval)

    def commit(self) -> None:

        def mark_tx():
            # mark the commit time of the transaction
            commit_time = time.time()
            for idx in range(len(self.ctx.block.txs)):
                memo: dict = json.loads(self.ctx.block.txs[idx].memo)
                ts = memo.get("ts", {})
                commit: List = ts.get(
                    "commit", []
                ) 
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

        mark_tx()
        index_tx()
        update_tx()
        self.blocks.append(self.ctx.block.as_str())
        # print(
        #     f"{time.time():.2f}, commit block({self.ctx.block.height}), num_txs={len(self.ctx.block.txs)}"
        # )
        self.ctx.reset()

    async def start(self) -> None:
        print("blockchain start!")
        self.status_manager.start_mining()
        self.status_manager.start_bc()
        while self.status_manager.is_running():
            if not self.status_manager.is_mining():
                await asyncio.sleep(1)
                continue
            try:
                # # execute block transactions in a limited time
                # await self.propose_block_and_exec()

                # no time limit, but limit the number of transactions in the block
                self.propose_block()
                await self.execute()

                # consensus time is separate
                await self.consensus()
                self.commit()
            except Exception as e:
                print("blockchain exeception: {}".format(traceback.format_exc()))
                break
            finally:
                pass
        print("blockchain stop!")

    # def stop_mining(self) -> bool:
    #     print("stop mining")
    #     self.status_manager.stop_mining()
    #     return True

    # def start_mining(self) -> bool:
    #     self.status_manager.start_mining()
    #     return True

    # def is_mining(self) -> bool:
    #     return self.status_manager.is_mining()

    def stop(self) -> None:
        print("stop blockchain")
        self.status_manager.stop_bc()

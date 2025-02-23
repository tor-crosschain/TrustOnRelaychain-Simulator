import time
import json
import asyncio
import threading
from chain_simulator.blockchain.blockchain import Blockchain
from chain_simulator.mempool.mempool import AsyncMemPool
from chain_simulator.config.config import Config
from chain_simulator.types.transaction import Transaction, TxStatus, TranMemo


def setup():
    pass


async def test_blockchain():
    # def work(pool):
    # SyncManager.register("mempool", callable=AsyncMemPool)
    # manager = multiprocessing.Manager()
    # mpool = manager.mempool(maxsize=5000, ctx=multiprocessing.get_context())
    TXNUM = 1000
    mpool = AsyncMemPool(maxsize=5000)

    cfg = Config()
    cfg.block_size = TXNUM
    cfg.block_interval = 1
    blockchain = Blockchain(pool=mpool, config=cfg)

    for i in range(TXNUM):
        tx = Transaction()
        tx.sender = "user-{}".format(i)
        tx.to = "base"
        tx.data = json.dumps({"arguments": [f"a{i}", i]})
        tx.memo = json.dumps({"type": TranMemo.CTXSRC})
        mpool.put_tx(tx)
    assert mpool.size() == TXNUM
    assert blockchain.txpool.size() == mpool.size()

    blockchain.propose_block()
    assert len(blockchain.blocks) == 1
    assert blockchain.ctx.block.height == 1
    assert len(blockchain.ctx.block.txs) == cfg.block_size

    await blockchain.execute()

    # check store
    print(f"store length: {blockchain.store.len()}")
    for i in range(TXNUM):
        key = f"a{i}"
        v = blockchain.store.get(key)
        assert v == f"{i}"
    # check tx status
    for tx in blockchain.ctx.block.txs:
        assert tx.status == TxStatus.SUCCESS, f"tx status not success! {tx.status}"

    starttime = time.time()
    await blockchain.consensus()
    endtime = time.time()
    assert (endtime - starttime - cfg.block_interval) < 1
    blockchain.commit()
    assert len(blockchain.blocks) == 2
    assert blockchain.ctx.block is None


def test_tx_proof():
    """test query tx proof from blockchain by txhash"""
    mpool = AsyncMemPool(maxsize=5000)

    cfg = Config()
    cfg.block_size = 2000
    cfg.block_interval = 1
    blockchain = Blockchain(pool=mpool, config=cfg)

    for i in range(1000):
        tx = Transaction()
        tx.sender = "user-{}".format(i)
        tx.to = "base"
        tx.data = json.dumps({"arguments": ["a", 10]})
        tx.memo = json.dumps({"ts": {}, "data": f"memo-{i}"})
        mpool.put_tx(tx)

    blockchain.propose_block()
    task_cs = blockchain.consensus()
    asyncio.run(
        asyncio.wait(
            [
                task_cs,
            ]
        )
    )

    maxbn = blockchain.block_num
    for i in range(1, maxbn + 1):
        txs = blockchain.blocks[i].txs
        for tx in txs:
            txhash = tx.hash()
            proof = blockchain.get_tx_proof(txhash)
            assert proof == txhash  
            proof_receipt = blockchain.get_tx_receipt_proof(txhash)
            assert proof_receipt == txhash  


def test_start_stop_mining():

    TXNUM = 200
    mpool = AsyncMemPool(maxsize=5000)

    cfg = Config()
    cfg.block_size = TXNUM
    cfg.block_interval = 1
    blockchain = Blockchain(pool=mpool, config=cfg)

    for i in range(TXNUM):
        tx = Transaction()
        tx.sender = "user-{}".format(i)
        tx.to = "base"
        tx.data = json.dumps({"arguments": [f"a{i}", i]})
        tx.memo = json.dumps({"type": TranMemo.CTXSRC})
        mpool.put_tx(tx)
    assert mpool.size() == TXNUM
    assert blockchain.txpool.size() == mpool.size()

    async def control():
        await asyncio.sleep(blockchain.config.block_interval * 3)
        blockchain.stop_mining()
        start_num = blockchain.block_num
        await asyncio.sleep(blockchain.config.block_interval * 3)
        end_num = blockchain.block_num

        assert (
            start_num == end_num or start_num + 1 == end_num
        ), f"start_num is {start_num}, end_num is {end_num} "
        blockchain.stop()
        await asyncio.sleep(1)

    async def main():
        # use gather instead of wait, otherwise no error
        await asyncio.gather(*[blockchain.start(), control()])

    asyncio.run(main())

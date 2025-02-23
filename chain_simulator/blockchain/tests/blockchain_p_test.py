import asyncio
from chain_simulator.blockchain.blockchain_p import (
    BlockchainMProc,
    BlockchainStates,
    BlockStorage,
    BaseStore,
)
from chain_simulator.types.transaction import TransactionIndexer
from chain_simulator.mempool.mempool import SyncMemPool
from chain_simulator.config.config import Config, XtxConfig


def gen_config():
    xtx_config = XtxConfig(
        dstids=[1, 2, 3, 4, 5],
        classes=[
            "Ethereum",
            "Ethereum",
            "Ethereum",
            "Tendermint",
            "Tendermint",
            "Tendermint",
        ],
        srcid=0,
    )
    return Config(
        gen_xtx_num=10,
        xtx_config=xtx_config,
    )


def gen_bc():
    block_storage = BlockStorage()
    transaction_indexer = TransactionIndexer()
    base_store = BaseStore()
    sync_mempool = SyncMemPool(maxsize=0)
    config = gen_config()
    blockchain_states = BlockchainStates(
        mp=sync_mempool,
        blocks=block_storage,
        store=base_store,
        txindexer=transaction_indexer,
        config=config,
    )
    bc = BlockchainMProc(config=config, bc_status_manager=blockchain_states)
    return bc


async def test_gen_xtx():
    bc = gen_bc()
    bc.status_manager.stop_gen_xtx()
    bc.propose_block()
    assert len(bc.ctx.block.txs) == 0
    bc.status_manager.start_gen_xtx()
    bc.propose_block()
    assert len(bc.ctx.block.txs) == bc.config.gen_xtx_num

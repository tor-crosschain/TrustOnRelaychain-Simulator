import sys
import os
import asyncio
import argparse
import threading
import uvloop

sys.path.insert(0, os.path.abspath("."))
from chain_simulator.service.api_service import ApiService
from chain_simulator.blockchain.blockchain_p import (
    BlockchainStates,
    BlockchainMProc,
    BlockStorage,
)
from chain_simulator.vm.store import BaseStore
from chain_simulator.types.transaction import TransactionIndexer
from chain_simulator.mempool.mempool import SyncMemPool
from chain_simulator.config.config import Config

# from chain_simulator.blockchain. import BlockchainStatesManager

asyncio.set_event_loop_policy(uvloop.EventLoopPolicy())


def get_args():
    parser = argparse.ArgumentParser()

    # read config first from file
    parser.add_argument("--cfg", type=str)

    # mempool config
    parser.add_argument("--mempool_size", type=int, default=1000)

    # block config
    parser.add_argument("--block_interval", type=int, default=1)
    parser.add_argument("--block_size", type=int, default=100)

    # server api config
    parser.add_argument("--api_port", type=int, default=8888)

    return parser.parse_args()


def start_api(config: Config, bcstates: BlockchainStates):
    api = ApiService(blockchain_states=bcstates)
    args = {"port": config.api_port}
    asyncio.run(api.run_app(args=args))


def start_bc(config: Config, bcstates: BlockchainStates):
    bcmp = BlockchainMProc(config=config, bc_status_manager=bcstates)
    asyncio.run(bcmp.start())


def schedule(cmd_args: dict):
    if cmd_args.cfg:
        config = Config.from_file(cmd_args.cfg)
    else:
        config = Config(
            mempool_size=cmd_args.mempool_size,
            block_interval=cmd_args.block_interval,
            block_size=cmd_args.block_size,
            api_port=cmd_args.api_port,
        )

    block_storage = BlockStorage()
    transaction_indexer = TransactionIndexer()
    base_store = BaseStore()
    sync_mempool = SyncMemPool(maxsize=cmd_args.mempool_size)
    blockchain_states = BlockchainStates(
        mp=sync_mempool,
        blocks=block_storage,
        store=base_store,
        txindexer=transaction_indexer,
        config=config,
    )

    proc_bc = threading.Thread(target=start_bc, args=(config, blockchain_states))
    proc_bc.start()

    proc_api = threading.Thread(
        target=start_api,
        args=(
            config,
            blockchain_states,
        ),
    )
    proc_api.start()

    proc_api.join()
    proc_bc.join()


if __name__ == "__main__":
    args = get_args()
    schedule(args)

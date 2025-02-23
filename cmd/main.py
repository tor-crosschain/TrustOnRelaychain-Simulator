import sys
import os
import asyncio
import argparse
import multiprocessing
import uvloop

sys.path.insert(0, os.path.abspath("."))
from chain_simulator.service.api_service import ApiService
from chain_simulator.blockchain.blockchain import Blockchain
from chain_simulator.mempool.mempool import AsyncMemPool
from chain_simulator.config.config import Config

asyncio.set_event_loop_policy(uvloop.EventLoopPolicy())


async def main(cmd_args):
    if cmd_args.cfg:
        config = Config.from_file(cmd_args.cfg)
    else:
        config = Config(
            mempool_size=cmd_args.mempool_size,
            block_interval=cmd_args.block_interval,
            block_size=cmd_args.block_size,
            api_port=cmd_args.api_port,
        )
    mpool = AsyncMemPool(maxsize=config.mempool_size)

    blockchain = Blockchain(pool=mpool, config=config)
    task_blockchain = blockchain.start()

    api_serv = ApiService(mpool=mpool, bc=blockchain)
    task_api = api_serv.run_app(args={"port": config.api_port})

    await asyncio.wait([task_blockchain, task_api])


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


if __name__ == "__main__":
    args = get_args()
    asyncio.run(main(args))

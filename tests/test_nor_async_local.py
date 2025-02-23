import math
import time
import requests
import asyncio
import json
import threading
import random
import multiprocessing
import sys, os

sys.path.insert(0, os.path.abspath("."))
from utils.request_helper import reqretry
from tornado.httpclient import AsyncHTTPClient
from typing import Tuple, List, Dict
from chain_simulator.types.transaction import TranMemo, Transaction
from chain_simulator.blockchain.blockchain import Blockchain
from chain_simulator.mempool.mempool import AsyncMemPool
from chain_simulator.config.config import Config
from relayer.connector.async_local_connector import AsyncLocalConnector
from relayer.relayer.relayer import Mode
from relayer.relayer.async_local_relayer import AsyncLocalRelayer

TXNUM = 500  # Total number of transactions
XTXNUM = int(TXNUM * 1.0)  # Cross-chain transaction ratio
CHAINNUM = 100  # Number of parallel chains
configs = [Config(block_size=100, block_interval=2, mempool_size=10000000)] * CHAINNUM
BASE_PORT = 12000

TPS_0 = min(*[x.block_size // x.block_interval for x in configs]) * CHAINNUM // 2
tempAsyncHttpClient = AsyncHTTPClient()


async def pre_test(
    chain_num: int,
    classes: List[int],  
):
    async def start(
        bcs: List[Blockchain],
        chain_num: int,
    ):
        cor_blockchains = []
        for i in range(chain_num):
            config = configs[i]
            mpool = AsyncMemPool(maxsize=config.mempool_size)
            print(f"create mpool: {mpool.maxsize}")
            bc = Blockchain(pool=mpool, config=config)
            print(f"create bc: {bc.txpool.maxsize}")
            print(f"bc id: {id(bc)}")
            bcs.append(bc)
            cor_blockchains.append(bc.start())
        await asyncio.gather(*cor_blockchains)

    bcs: List[Blockchain] = []
    assert len(classes) == 2, "chain class num must be 2"
    classes: List[str] = ["Ethereum"] * classes[0] + ["Tendermint"] * classes[1]

    task_pre = asyncio.create_task(start(bcs, chain_num))

    await asyncio.sleep(0.5)

    assert len(bcs) == chain_num

    return task_pre, bcs, classes


async def send_tx_chain(paraid: int, bc: Blockchain, classes: List[str]):
    dsts = [-1] * (TXNUM - XTXNUM) + [1] * XTXNUM
    dsts = random.sample(dsts, len(dsts))
    for i in range(len(dsts)):
        if dsts[i] == 1:
            x = None
            while True:
                x = random.randint(0, CHAINNUM - 1) 
                if x != paraid:  # Select a non-chain identifier
                    break
            assert x is not None
            dsts[i] = x

    for idx in range(TXNUM):
        if dsts[idx] >= 0:  
            dstid = int(dsts[idx])
            memo = {"type": TranMemo.CTXSRC, "dst": dsts[idx]}
            # Source chain timestamp
            memo["ts"] = {"init": time.time()}
            data = {
                "tx": {
                    "sender": f"send/{paraid}/{idx}",
                    "to": "lightclient",
                    "data": json.dumps(
                        {
                            "func": "app_init",
                            "arguments": [dstid, classes[dstid], "crosschain-data"],
                        }
                    ),
                    "memo": json.dumps(memo),
                }
            }
        else:
            memo = {"type": "TX"}
            # Source chain timestamp
            memo["ts"] = {"init": time.time()}
            data = {
                "tx": {
                    "sender": f"send/{paraid}/{idx}",
                    "to": "base",
                    "data": json.dumps({"arguments": [f"a{idx}", idx]}),
                    "memo": json.dumps(memo),
                }
            }

        tx = Transaction(**data["tx"])
        ret = await bc.txpool.put_tx(tx)
        assert ret
        # await reqretry(asyncHttpClient, url=url_send_tx, params=data, method="POST")
        if idx % 20 == 0:
            print(f"sendtx to {paraid}: {idx}, time: {time.time()}")
        await asyncio.sleep(0.005)
    print(f"sendtx to {paraid} finished!")


async def send_tx_proc(bcs: List[Blockchain], classes: List[str]):
    tasks: List[asyncio.Task] = []
    for idx, bc in enumerate(bcs):
        task = asyncio.create_task(send_tx_chain(paraid=idx, bc=bc, classes=classes))
        tasks.append(task)
    await asyncio.sleep(0.01)
    for task in tasks:
        while not task.done():
            await asyncio.sleep(0.1)


def build_relayers(
    bcs: List[Blockchain],
) -> List[Tuple[AsyncLocalRelayer, AsyncLocalRelayer]]:

    relayer_pairs = []
    lh = len(bcs)
    # relayer_pairs_queue = multiprocessing.Manager().Queue()

    def create_relayers(i: int):
        for j in range(i + 1, lh):
            # starttime = time.time()
            src_connector = AsyncLocalConnector(bc=bcs[i], sender=f"proc/{i}/{j}/src")
            tgt_connector = AsyncLocalConnector(bc=bcs[j], sender=f"proc/{i}/{j}/dst")

            relayer0 = AsyncLocalRelayer(
                src_connector, tgt_connector, mode=Mode.MODENOR
            )
            relayer1 = AsyncLocalRelayer(
                tgt_connector, src_connector, mode=Mode.MODENOR
            )
            relayer_pairs.append((relayer0, relayer1))
            print(f"relay between ({relayer0.src.pid}, {relayer0.dst.pid})")
            assert relayer0.src.pid == i, f"src pid is { relayer0.src.pid }"
            assert relayer0.dst.pid == j, f"dsr pid is { relayer0.dst.pid }"

    for i in range(lh):
        create_relayers(i)

    return relayer_pairs


async def start_relayers(
    relayer_pairs: List[Tuple[AsyncLocalRelayer, AsyncLocalRelayer]]
):
    async def start():
        cors = []
        for rly0, rly1 in relayer_pairs:
            cor0 = rly0.start_one_way()
            cor1 = rly1.start_one_way()
            cors.append(cor0)
            cors.append(cor1)
        await asyncio.gather(*cors)

    task = asyncio.create_task(start())
    await asyncio.sleep(0.01)
    return task


async def check(
    idx: int,
    bc: Blockchain,
    target: int,
    states: dict,
    ctxs: multiprocessing.Queue,
):
    tempctxs = []
    assert isinstance(bc, Blockchain)
    assert isinstance(target, int)
    # asyncHttpClient = AsyncHTTPClient()
    # url = f"http://{host}/query_block_number"
    # resp = await reqretry(asyncHttpClient, url, method="GET")
    # bn = int(resp["msg"])
    bn = bc.block_num
    i = 1
    while True:
        if i > bn:
            while True:
                bn = bc.block_num
                if i <= bn:
                    break
                await asyncio.sleep(configs[idx].block_interval)
        print(f"check block: {i}")
        block = bc.get_block_by_height(height=i)
        assert block.height == i
        txs = block.txs
        for tx in txs:
            memo = json.loads(tx.memo)
            if memo["type"] == TranMemo.CTXDST:
                tempctxs.append(memo)
                states["val"] += 1
                # print(f"inter val: {states['val']}")
                last_commit = memo["ts"]["commit"][-1]
                init = memo["ts"]["init"]
                states["latency_sum"] += last_commit - init
                if states["min_init"] > init:
                    states["min_init"] = init
                if states["max_last_commit"] < last_commit:
                    states["max_last_commit"] = last_commit
        if states["val"] >= target:
            print(f"val: {states['val']}")
            break
        i += 1
        await asyncio.sleep(0.05)
        # print(f"val.value: {val.value}, target: {target}")
    for item in tempctxs:
        await ctxs.put(item)


async def wait_check(bcs: List[Blockchain]):
    states = {
        "val": 0,
        "min_init": time.time() * 2,
        "max_last_commit": 0,
        "latency_sum": 0,
    }
    target = XTXNUM * CHAINNUM
    ctxs = asyncio.Queue()
    cors = []
    for idx, bc in enumerate(bcs):
        cor = check(idx, bc, target, states, ctxs)
        cors.append(cor)
    await asyncio.gather(*cors)
    return (
        ctxs,
        target,
        states["min_init"],
        states["max_last_commit"],
        states["latency_sum"],
    )


async def set_paraid(bc: Blockchain, paraid: int):
    memo = json.dumps({"type": "TX"})
    data = json.dumps({"func": "set_paraid", "arguments": [paraid]})

    tx = Transaction(
        sender=f"send/{paraid}/set_paraid", to="lightclient", memo=memo, data=data
    )
    ret = await bc.txpool.put_tx(tx)
    assert ret


async def set_paratype(bc: Blockchain, paratype: str):
    memo = json.dumps({"type": "TX"})
    data = json.dumps({"func": "set_paratype", "arguments": [paratype]})

    tx = Transaction(
        sender=f"send/{paratype}/{set_paratype}", to="lightclient", memo=memo, data=data
    )
    ret = await bc.txpool.put_tx(tx)
    assert ret
    print(f"bc id: {id(bc)}")
    print(f"bc.txpool.qsize: {bc.txpool.size()}")


async def set_crossinfo(bcs: List[Blockchain], classes: List[str]):
    for paraid, bc in enumerate(bcs):
        print(f"bc.txpool.size: {bc.txpool.maxsize}")
        await set_paraid(bc, paraid)
        await set_paratype(bc, classes[paraid])


def stop_mining(host: str):
    print(f"stop mining: {host}")
    url = f"http://{host}/stop_mining"
    cor_stopmining = reqretry(tempAsyncHttpClient, url, method="POST")
    return cor_stopmining


def stop_all_mining(bcs: List[Blockchain]):
    for bc in bcs:
        bc.stop_mining()


def start_all_mining(bcs: List[Blockchain]):
    for bc in bcs:
        bc.start_mining()


async def stop_relay(
    relayer_pairs: List[Tuple[AsyncLocalRelayer, AsyncLocalRelayer]], task: asyncio.Task
):
    for (rly0, rly1) in relayer_pairs:
        rly0.stop()
        rly1.stop()
    while not task.done():
        await asyncio.sleep(0.1)
    assert task.done()


async def stop_bc(bcs: List[Blockchain], task: asyncio.Task):
    for bc in bcs:
        bc.stop()
    while not task.done():
        await asyncio.sleep(0.1)
    assert task.done()


async def test_nor_async():
    """Test cross-chain interaction between chain_num chains, using the two-way direct connection mode between chains, so any two chains have a gateway;
    The number of transactions sent to each chain is fixed, the cross-chain transaction ratio is fixed, and the destination chain identifier of the cross-chain transaction is random;
    """
    classone = CHAINNUM // 2
    classtwo = CHAINNUM - classone
    task_pre, bcs, classes = await pre_test(
        chain_num=CHAINNUM, classes=[classone, classtwo]
    )
    # Wait for all tasks to start
    await asyncio.sleep(0.01)

    # Set chain id, chain type
    await set_crossinfo(bcs, classes)
    print("============set_crossinfo finished!============" + str(int(time.time())))

    # Wait for each chain to include the set paraid/paratype transaction
    await asyncio.sleep(configs[0].block_interval * 2)

    # Stop mining
    stop_all_mining(bcs)
    print("============stop all mining finished!============" + str(int(time.time())))

    # Build relayer
    relayer_pairs = build_relayers(bcs)
    print("============start relayers finished!============" + str(int(time.time())))

    # Start relayer
    task_rly = await start_relayers(relayer_pairs)

    # Start mining
    start_all_mining(bcs)
    print("============start all mining finished!============" + str(int(time.time())))

    # Send transactions to each chain in parallel
    # await send_tx(hosts, classes=classes)
    await send_tx_proc(bcs, classes)
    print("============process sendtx finished!============" + str(int(time.time())))

    # Check if the number of transactions with memo.type == CTX-DST on all chains is the same as the number of cross-chain transactions
    (ctxs, target, min_init, max_last_commit, latency_sum) = await wait_check(bcs)
    print("============wait check finished!============" + str(int(time.time())))

    # Close relayer
    await stop_relay(relayer_pairs, task_rly)
    print("============close relayer!============" + str(int(time.time())))

    # Close blockchain and service
    await stop_bc(bcs, task_pre)
    print("============close bcs and api servs!============" + str(int(time.time())))

    ts_src = []
    ts_rly = []
    ts_dst = []
    while not ctxs.empty():
        memo = await ctxs.get()
        # memostr = ctxs.get()
        # memo = json.loads(memostr)
        ts = memo["ts"]
        ts_src.append(ts["commit"][0] - ts["init"])
        rly = ts["relayer"]
        assert rly[2][0] == "send", f"relayer ts tag({rly[2][0]}) is invalid, {rly}"
        assert rly[0][0] == "listened", f"relayer ts tag({rly[0][0]}) is invalid"
        ts_rly.append(ts["relayer"][2][1] - ts["relayer"][0][1])
        ts_dst.append(ts["commit"][1] - ts["relayer"][2][1])
    ts_src_avg = sum(ts_src) / len(ts_src)
    ts_rly_avg = sum(ts_rly) / len(ts_rly)
    ts_dst_avg = sum(ts_dst) / len(ts_dst)

    tps = target / (max_last_commit - min_init)
    latency_avg = latency_sum / target
    print(f"tps: {tps}")
    print("tps ratio: {:.2f}%".format((tps / TPS_0) * 100))
    print(f"latency avg: {latency_avg}")
    print(f"ts_src_avg: {ts_src_avg}")
    print(f"ts_rly_avg: {ts_rly_avg}")
    print(f"ts_dst_avg: {ts_dst_avg}")


if __name__ == "__main__":
    starttime = time.perf_counter()
    asyncio.run(test_nor_async())
    endtime = time.perf_counter()
    print(f"time cost: {endtime-starttime}")

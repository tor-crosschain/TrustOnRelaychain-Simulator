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
from chain_simulator.types.transaction import TranMemo
from chain_simulator.types.block import Block
from chain_simulator.service.api_service import ApiService
from chain_simulator.blockchain.blockchain import Blockchain
from chain_simulator.mempool.mempool import AsyncMemPool
from chain_simulator.config.config import Config
from relayer.connector.async_connector import AsyncConnector
from relayer.relayer.relayer import Mode
from relayer.relayer.async_relayer import AsyncRelayer

TXNUM = 500  # Total number of transactions
XTXNUM = int(TXNUM * 1.0)  # Cross-chain transaction ratio
CHAINNUM = 2  # Number of parallel chains
configs = [Config(block_size=100, block_interval=2, mempool_size=10000000)] * CHAINNUM
BASE_PORT = 12000

TPS_0 = min(*[x.block_size // x.block_interval for x in configs]) * CHAINNUM // 2
tempAsyncHttpClient = AsyncHTTPClient()


async def start_bcapi(
    chain_num: int,
    classes: List[int], 
):
    async def start_async(
        hosts: List[str],
        args: List[Dict[str, int]],
        bcs: List[Blockchain],
        api_servs: List[ApiService],
    ):
        lh = len(hosts)
        cor_api_servs = []
        cor_blockchains = []
        for i in range(lh):
            config = configs[i]
            mpool = AsyncMemPool(maxsize=config.mempool_size)
            bc = Blockchain(pool=mpool, config=config)
            api_serv = ApiService(mpool=mpool, bc=bc)
            bcs.append(bc)
            api_servs.append(api_serv)
            cor_api_servs.append(api_serv.run_app(args[i]))
            cor_blockchains.append(bc.start())
        await asyncio.gather(*(cor_api_servs + cor_blockchains))

    async def listen_stop(
        stop_event: threading.Event,
        bcs: List[Blockchain],
        api_servs: List[ApiService],
    ):
        while not stop_event.is_set():
            await asyncio.sleep(1)
        for bc in bcs:
            bc.stop()
        for api in api_servs:
            api.stop_event.set()

    async def schedule(
        hosts: List[str],
        args: List[Dict[str, int]],
        stop_event: threading.Event,
    ):
        bcs: List[Blockchain] = []
        api_servs: List[ApiService] = []

        task_listen = asyncio.create_task(listen_stop(stop_event, bcs, api_servs))
        await asyncio.sleep(0.5)

        await start_async(hosts, args, bcs, api_servs)

        # check task stop
        await asyncio.sleep(0.5)
        assert task_listen.done()

    def start(
        hosts: List[str],
        args: List[Dict[str, int]],
        stop_event: threading.Event,
    ):
        asyncio.run(schedule(hosts, args, stop_event))

    cluster_size = 2
    assert len(classes) == 2, "chain class num must be 2"
    classes: List[str] = ["Ethereum"] * classes[0] + ["Tendermint"] * classes[1]
    hosts: List[str] = []
    args: List[Dict[str, int]] = []
    for i in range(chain_num):
        arg = {"port": 12000 + i}
        hosts.append(f"localhost:{arg['port']}")
        args.append(arg)

    hosts_by_cluster = [
        hosts[i : i + cluster_size] for i in range(0, chain_num, cluster_size)
    ]
    args_by_cluster = [
        args[i : i + cluster_size] for i in range(0, chain_num, cluster_size)
    ]
    assert len(hosts_by_cluster) == len(args_by_cluster)

    procs: List[multiprocessing.Process] = []
    stop_event = multiprocessing.Manager().Event()
    for (hosts_cluster, args_cluster) in zip(hosts_by_cluster, args_by_cluster):
        proc = multiprocessing.Process(
            target=start, args=(hosts_cluster, args_cluster, stop_event)
        )
        procs.append(proc)

    for proc in procs:
        proc.start()

    return procs, stop_event, hosts, classes


async def send_tx_chain(paraid: int, host: str, classes: List[str]):
    dsts = [-1] * (TXNUM - XTXNUM) + [1] * XTXNUM
    dsts = random.sample(dsts, len(dsts))
    for i in range(len(dsts)):
        if dsts[i] == 1:
            x = None
            while True:
                x = random.randint(0, CHAINNUM - 1)  # Randomly select the destination chain identifier
                if x != paraid:  # Select a destination chain identifier that is not the current chain
                    break
            assert x is not None
            dsts[i] = x
    url_send_tx = f"http://{host}/send_tx"
    asyncHttpClient = AsyncHTTPClient()
    for idx in range(TXNUM):
        if dsts[idx] >= 0:  # Determine if it is a cross-chain transaction
            # Send a transaction to the app_init function of the lightclient contract
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
        await reqretry(asyncHttpClient, url=url_send_tx, params=data, method="POST")
        if idx % 20 == 0:
            print(f"sendtx to {paraid}: {idx}, time: {time.time()}")
        # await asyncio.sleep(0.01)
    print(f"sendtx to {paraid} finished!")


async def send_tx_proc(hosts: List[str], classes: List[str]):
    def main(paraid, host, classes):
        asyncio.run(send_tx_chain(paraid, host, classes))

    procs: List[multiprocessing.Process] = []
    for paraid, host in enumerate(hosts):
        proc = multiprocessing.Process(target=main, args=(paraid, host, classes))
        procs.append(proc)

    for proc in procs:
        proc.start()

    for proc in procs:
        if proc.is_alive():
            await asyncio.sleep(1)
        else:
            proc.join()


def build_and_start_relayers(hosts: List[str]):
    async def create(srcid: int, dstid: int, relayers: List[AsyncRelayer]):
        # starttime = time.time()
        src_connector = await AsyncConnector.new(
            host=hosts[srcid], sender=f"proc/{srcid}/{dstid}/src"
        )
        tgt_connector = await AsyncConnector.new(
            host=hosts[dstid], sender=f"proc/{srcid}/{dstid}/dst"
        )
        relayer = AsyncRelayer(src_connector, tgt_connector, mode=Mode.MODENOR)
        relayers.append(relayer)
        print(f"relay from ({relayer.src.pid}, {relayer.dst.pid})")
        assert relayer.src.pid == srcid, f"src pid is { relayer.src.pid }"
        assert relayer.dst.pid == dstid, f"dsr pid is { relayer.dst.pid }"

    async def create_relayers(paraid: int, hosts: List[str]):
        lh = len(hosts)
        cors = []
        relayers: List[AsyncRelayer] = []
        for i in range(lh):
            if paraid == i:
                continue
            cor = create(paraid, i, relayers)
            cors.append(cor)
        await asyncio.gather(*cors)
        return relayers

    async def start_relayers(relayers: List[AsyncRelayer]):
        cors = []
        for rly in relayers:
            cor = rly.start_one_way()
            cors.append(cor)
        await asyncio.gather(*cors)

    async def listen_stop(relayers: List[AsyncRelayer], stopevent: threading.Event):
        while not stopevent.is_set():
            await asyncio.sleep(1)
        for rly in relayers:
            rly.stop()

    async def schedule(paraid: int, hosts: List[str], stopevent: threading.Event):
        # create
        relayers = await create_relayers(paraid, hosts)

        # listen stop event
        cor = listen_stop(relayers, stopevent)
        task = asyncio.create_task(cor)
        await asyncio.sleep(0.5)

        # start
        await start_relayers(relayers)

        # check task stop
        await asyncio.sleep(0.5)
        assert task.done()

    def relay(paraid: int, hosts: List[str], rly_proc_stop_event: threading.Event):
        asyncio.run(schedule(paraid, hosts, rly_proc_stop_event))

    lh = len(hosts)
    procs: List[multiprocessing.Process] = []
    rly_proc_stop_event = multiprocessing.Manager().Event()
    for idx in range(lh):
        proc = multiprocessing.Process(
            target=relay, args=(idx, hosts, rly_proc_stop_event)
        )
        procs.append(proc)

    for proc in procs:
        proc.start()

    return procs, rly_proc_stop_event


async def check(
    idx: int,
    host: str,
    target: int,
    states: dict,
    ctxs: multiprocessing.Queue,
):
    tempctxs = []
    assert isinstance(host, str)
    assert isinstance(target, int)
    asyncHttpClient = AsyncHTTPClient()
    url = f"http://{host}/query_block_number"
    resp = await reqretry(asyncHttpClient, url, method="GET")
    bn = int(resp["msg"])
    i = 1
    while True:
        if i > bn:
            while True:
                url = f"http://{host}/query_block_number"
                resp = await reqretry(asyncHttpClient, url, method="GET")
                bn = int(resp["msg"])
                if i <= bn:
                    break
                await asyncio.sleep(configs[idx].block_interval)
        print(f"check block: {i}")
        url_block = f"http://{host}/query_block?bn={i}"
        resp = await reqretry(asyncHttpClient, url_block, method="GET")
        blk: dict = json.loads(resp["msg"])
        assert blk["height"] == i
        block = Block.from_json(blk)
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
        await asyncio.sleep(0.01)
        # print(f"val.value: {val.value}, target: {target}")
    for item in tempctxs:
        await ctxs.put(item)


async def wait_check(hosts: List[str]):
    states = {
        "val": 0,
        "min_init": time.time() * 2,
        "max_last_commit": 0,
        "latency_sum": 0,
    }
    target = XTXNUM * CHAINNUM
    ctxs = asyncio.Queue()
    cors = []
    for idx, host in enumerate(hosts):
        cor = check(idx, host, target, states, ctxs)
        cors.append(cor)
    await asyncio.gather(*cors)
    return (
        ctxs,
        target,
        states["min_init"],
        states["max_last_commit"],
        states["latency_sum"],
    )


def set_paraid(host: str, paraid: int):
    url_set_id = f"http://{host}/send_tx"
    memo = {"type": "TX"}
    data = {
        "tx": {
            "sender": f"send/{paraid}/{set}",
            "to": "lightclient",
            "data": json.dumps({"func": "set_paraid", "arguments": [paraid]}),
            "memo": json.dumps(memo),
        }
    }
    cor_setid = reqretry(
        tempAsyncHttpClient, url=url_set_id, params=data, method="POST"
    )
    return cor_setid


def set_paratype(host: str, paratype: str):
    url_set_type = f"http://{host}/send_tx"
    memo = {"type": "TX"}
    data = {
        "tx": {
            "sender": f"send/{paratype}/{set}",
            "to": "lightclient",
            "data": json.dumps({"func": "set_paratype", "arguments": [paratype]}),
            "memo": json.dumps(memo),
        }
    }

    cor_settype = reqretry(
        tempAsyncHttpClient, url=url_set_type, params=data, method="POST"
    )
    return cor_settype


async def set_crossinfo(hosts: List[str], classes: List[str]):
    cors = []
    for paraid, host in enumerate(hosts):
        cor_setid = set_paraid(host, paraid)
        cor_settype = set_paratype(host, classes[paraid])
        cors.extend([cor_setid, cor_settype])
    await asyncio.gather(*cors)


def stop_mining(host: str):
    print(f"stop mining: {host}")
    url = f"http://{host}/stop_mining"
    cor_stopmining = reqretry(tempAsyncHttpClient, url, method="POST")
    return cor_stopmining


async def stop_all_mining(hosts: List[str]):
    cors = []
    for host in hosts:
        cor = stop_mining(host)
        cors.append(cor)
    await asyncio.gather(*cors)


def start_mining(host: str):
    print(f"start mining: {host}")
    url = f"http://{host}/start_mining"
    cor_startmining = reqretry(tempAsyncHttpClient, url, method="POST")
    return cor_startmining


async def start_all_mining(hosts: List[str]):
    cors = []
    for host in hosts:
        cor = start_mining(host)
        cors.append(cor)
    await asyncio.gather(*cors)


async def stop_async_proc(
    stop_event: threading.Event, procs: List[multiprocessing.Process]
):
    stop_event.set()
    for proc in procs:
        if proc.is_alive():
            await asyncio.sleep(1)
        else:
            proc.join()


async def stop_relay(stop_event: threading.Event, procs: List[multiprocessing.Process]):
    await stop_async_proc(stop_event, procs)


async def stop_bc_api(
    stop_event: threading.Event, procs: List[multiprocessing.Process]
):
    await stop_async_proc(stop_event, procs)


async def test_nor_async():
    """Test cross-chain interaction between chain_num chains, using the two-way direct connection mode between chains, so any two chains have a gateway;
    The number of transactions sent to each chain is fixed, the cross-chain transaction ratio is fixed, and the destination chain identifier of the cross-chain transaction is random;
    """
    classone = CHAINNUM // 2
    classtwo = CHAINNUM - classone
    procs_bcapi, stop_event_bcapi, hosts, classes = await start_bcapi(
        chain_num=CHAINNUM, classes=[classone, classtwo]
    )
    # Wait for all procs to start
    await asyncio.sleep(1)

    # Set chain id, chain type
    await set_crossinfo(hosts, classes)
    print("============set_crossinfo finished!============" + str(int(time.time())))

    # Wait for each chain to include the set paraid/paratype transaction
    await asyncio.sleep(configs[0].block_interval * 2)

    # Stop mining
    await stop_all_mining(hosts)
    print("============stop all mining finished!============" + str(int(time.time())))

    # Build relayer
    # relayer_pairs = await build_relayers(hosts)
    # relayer_cluster = await build_relayers_cluster(hosts)

    # Start relay process
    # procc_rly = start_relayers_proc(relayer_cluster)
    # task_relayers = start_relayers(relayer_pairs)

    # Build and start relayer, each chain's relayers run in a process in an asynchronous form
    rly_procs, rly_stop_event = build_and_start_relayers(hosts)
    await asyncio.sleep(1)
    print("============start relayers finished!============" + str(int(time.time())))

    # Start mining
    await start_all_mining(hosts)
    print("============start all mining finished!============" + str(int(time.time())))

    # Send transactions to each chain in parallel
    # await send_tx(hosts, classes=classes)
    await send_tx_proc(hosts, classes)
    print("============process sendtx finished!============" + str(int(time.time())))

    # Check if the number of transactions with memo.type == CTX-DST on all chains is the same as the number of cross-chain transactions
    (ctxs, target, min_init, max_last_commit, latency_sum) = await wait_check(hosts)
    print("============wait check finished!============" + str(int(time.time())))

    # Close relayer
    await stop_relay(rly_stop_event, rly_procs)
    print("============close relayer!============" + str(int(time.time())))

    # Close blockchain and service
    await stop_bc_api(stop_event_bcapi, procs_bcapi)
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
        assert rly[2][0] == "send", f"relayer ts tag({rly[2][0]}) is invalid"
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

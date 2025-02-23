"""
Containers are created by ansible, then run_nor.py creates relayers and monitors completion flags
"""
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
from multiprocessing import synchronize
from typing import Tuple, List
from chain_simulator.types.transaction import TranMemo
from chain_simulator.types.block import Block
from chain_simulator.service.api_service import ApiService
from chain_simulator.blockchain.blockchain import Blockchain
from chain_simulator.mempool.mempool import AsyncMemPool
from chain_simulator.config.config import Config
from relayer.connector.connector import Connector
from relayer.relayer.relayer import Relayer, Mode

TXNUM = 200  # Total number of transactions
XTXNUM = int(TXNUM * 1.0)  # Cross-chain transaction ratio
CHAINNUM = 3  # Number of parachains
configs = [Config(block_size=100, block_interval=1, mempool_size=1000000)] * CHAINNUM

TPS_0 = min(*[x.block_size // x.block_interval for x in configs]) * CHAINNUM // 2


def pre_test(
    chain_num: int,
    class_num: List[int],
) -> Tuple[
    List[multiprocessing.Process],
    List[str],
    List[Tuple[synchronize.Event, synchronize.Event]],
    List[str],
]:
    def thread_proxy(
        args: dict,
        stop_api_event: multiprocessing.Event,
        stop_bc_event: multiprocessing.Event,
        config: Config,
    ):
        """run tornado service in a seperate thread

        :param serv: tornado api service
        :type serv: ApiService
        """

        mpool = AsyncMemPool(maxsize=config.mempool_size)
        bc = Blockchain(pool=mpool, config=config)
        api_serv = ApiService(mpool=mpool, bc=bc)
        cors = [api_serv.run_app(args), bc.start()]

        # NOTE
        # stop a coroutine in a thread by using await asyncio.event(),
        # then asyncio.set() must also be in the same thread
        # In other words, await and set must be in the same loop
        async def stopapiserv():
            while True:
                if stop_api_event.is_set():
                    break
                await asyncio.sleep(1)
            api_serv.stop_event.set()
            await asyncio.sleep(0.5)

        async def stopbc():
            while True:
                if stop_bc_event.is_set():
                    break
                await asyncio.sleep(1)
        
            bc.stop()
            await asyncio.sleep(config.block_interval)  # Wait for a consensus cycle

        cors += [stopapiserv(), stopbc()]
        # NOTE
        # asyncio.run() will cancel all tasks which is not task.done()
        # task.cancel() won't stop tornado service normally
        # you must set ApiService.stop_event to stop it
        # because it waits for asyncio.Event() asynchronously
        asyncio.run(
            asyncio.wait(
                cors,
            )
        )
        print(f"process-{multiprocessing.current_process().name} stopped!")

    procs: List[multiprocessing.Process] = []
    hosts: List[str] = []
    events: List[Tuple[multiprocessing.Event, multiprocessing.Event]] = []
    assert len(class_num) == 2, "chain class num must be 2"
    classes: List[str] = ["Ethereum"] * class_num[0] + ["Tendermint"] * class_num[1]
    for i in range(chain_num):
        args = {"port": 9000 + i}
        hosts.append(f"localhost:{args['port']}")

        stop_api_event = multiprocessing.Event()
        stop_bc_event = multiprocessing.Event()
        events.append((stop_api_event, stop_bc_event))
        proc = multiprocessing.Process(
            target=thread_proxy,
            args=(args, stop_api_event, stop_bc_event, configs[i]),
        )
        procs.append(proc)

    for proc in procs:
        proc.start()

    time.sleep(1) 

    return procs, hosts, events, classes


def send_tx(chainnum: int, paraid: int, host: str, txnum: int) -> None:
    # The destination chain identifier of all transactions, if the identifier is 0, it is a normal transaction, if the identifier is not 0, it is a cross-chain transaction, and the identifier is the destination chain identifier
    dsts = [0] * XTXNUM + [1] * (TXNUM - XTXNUM)
    dsts = random.sample(dsts, len(dsts))
    for i in range(len(dsts)):
        if dsts[i] == 0:
            x = None
            while True:
                x = random.randint(0, CHAINNUM - 1) 
                if x != paraid:  
                    break
            assert x is not None
            dsts[i] = x
    url_send_tx = f"http://{host}/send_tx"
    for idx in range(TXNUM):
        if dsts[idx] >= 0: 
            memo = {"type": TranMemo.CTXSRC, "dst": dsts[idx]}
        else:
            memo = {"type": "TX"}

        memo["ts"] = {"init": time.time()}
        memo["mode"] = TranMemo.MODENOR
        data = {
            "tx": {
                "sender": f"send/{paraid}/{idx}",
                "to": "base",
                "data": json.dumps({"arguments": [f"a{idx}", idx]}),
                "memo": json.dumps(memo),
            }
        }
        resp_send_tx = requests.post(url=url_send_tx, data=json.dumps(data), timeout=10)
        assert resp_send_tx.status_code == 200
        resp = json.loads(resp_send_tx.text)
        assert resp["error"] == "", f"response error: {resp['error']}"
        assert resp["code"] == 200, f"response code: {resp['code']}"

    print(f"send to {paraid} ok")


def send_tx_parallelism(hosts: List[str]) -> List[multiprocessing.Process]:
    procs: List[multiprocessing.Process] = []
    txnum = 20
    for paraid, host in enumerate(hosts):
        proc = multiprocessing.Process(
            target=send_tx, args=(len(hosts), paraid, host, txnum)
        )
        procs.append(proc)

    for proc in procs:
        proc.start()

    return procs


def build_relayers(hosts: List[str]) -> List[Tuple[Relayer, Relayer]]:
    relayer_pairs = []
    lh = len(hosts)
    for i in range(lh):
        for j in range(i + 1, lh):
            src_connector = Connector(host=hosts[i], sender=f"proc/{i}/{j}/src")
            tgt_connector = Connector(host=hosts[j], sender=f"proc/{i}/{j}/dst")
            relayer0 = Relayer(src_connector, tgt_connector, mode=Mode.MODENOR)
            relayer1 = Relayer(tgt_connector, src_connector, mode=Mode.MODENOR)
            relayer_pairs.append((relayer0, relayer1))
            print(f"relay between ({relayer0.src.pid}, {relayer0.dst.pid})")
            assert relayer0.src.pid == i, f"src pid is { relayer0.src.pid }"
            assert relayer0.dst.pid == j, f"dsr pid is { relayer0.dst.pid }"
    return relayer_pairs


def check(
    idx: int,
    host: str,
    val,
    target: int,
    min_init,
    max_last_commit,
    latency_sum,
):
    assert isinstance(host, str)
    assert isinstance(target, int)
    url = f"http://{host}/query_block_number"
    r = requests.get(url)
    resp = json.loads(r.text)
    bn = int(resp["msg"])
    i = 1
    while True:
        if i > bn:
            while True:
                url = f"http://{host}/query_block_number"
                r = requests.get(url)
                resp = json.loads(r.text)
                bn = int(resp["msg"])
                if i <= bn:
                    break
                time.sleep(configs[idx].block_interval)
        url_block = f"http://{host}/query_block?bn={i}"
        r = requests.get(url_block)
        resp = json.loads(r.text)
        blk: dict = json.loads(resp["msg"])
        assert blk["height"] == i
        block = Block.from_json(blk)
        txs = block.txs
        for tx in txs:
            memo = json.loads(tx.memo)
            if memo["type"] == TranMemo.CTXDST:
                with val.get_lock():
                    val.value += 1
                last_commit = memo["ts"]["commit"][-1]
                init = memo["ts"]["init"]
                with latency_sum.get_lock():
                    latency_sum.value += last_commit - init
                with min_init.get_lock():
                    if min_init.value > init:
                        min_init.value = init
                with max_last_commit.get_lock():
                    if max_last_commit.value < last_commit:
                        max_last_commit.value = last_commit
        with val.get_lock():
            if val.value >= target:
                print(f"val.value: {val.value}")
                return
        i += 1
        print(f"val.value: {val.value}, target: {target}")


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
    resp_send_tx = requests.post(url_set_id, data=json.dumps(data), timeout=10)
    assert resp_send_tx.status_code == 200
    resp = json.loads(resp_send_tx.text)
    assert resp["error"] == "", f"response error: {resp['error']}"
    assert resp["code"] == 200, f"response code: {resp['code']}"


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
    resp_send_tx = requests.post(url_set_type, data=json.dumps(data), timeout=10)
    assert resp_send_tx.status_code == 200
    resp = json.loads(resp_send_tx.text)
    assert resp["error"] == "", f"response error: {resp['error']}"
    assert resp["code"] == 200, f"response code: {resp['code']}"


def set_crossinfo(hosts: List[str], classes: List[str]):
    for paraid, host in enumerate(hosts):
        set_paraid(host, paraid)
        set_paratype(host, classes[paraid])


def read_args() -> [List[str], List[str]]:
    hosts = [
        "10.21.4.31:9001",
        "10.21.4.31:9002",
        "10.21.4.35:9001",
    ]

    classes = ["Tendermint", "Tendermint", "Tendermint"]

    return hosts, classes


def main():
    """Test cross-chain interaction between chain_num chains, the chains use two-way direct connection mode, so any two chains have a gateway;
    The number of transactions sent to each chain is fixed, the cross-chain transaction ratio is fixed, and the destination chain identifier of the cross-chain transaction is random;
    """
    hosts, classes = read_args()

    # Set chain id, chain type
    set_crossinfo(hosts, classes)

    # Send transactions to each chain in parallel
    procs_sendtx = send_tx_parallelism(hosts)


    # Wait for each chain to pack the set paraid/paratype transaction
    time.sleep(configs[0].block_interval * 2)

    # Build relayer
    relayer_pairs = build_relayers(hosts)

    # Start relay process
    procs_rly: List[Tuple[multiprocessing.Process, multiprocessing.Process]] = []
    for rly0, rly1 in relayer_pairs:
        proc1 = multiprocessing.Process(target=rly0.start_one_way)
        proc2 = multiprocessing.Process(target=rly1.start_one_way)
        procs_rly.append((proc1, proc2))
    for proc0, proc1 in procs_rly:
        proc0.start()
        proc1.start()

    # Wait for the transaction sending process to end
    for proc in procs_sendtx:
        proc.join()
    print("============process sendtx finished!")

    # Check if the number of transactions with memo.type == CTX-DST on all chains is the same as the number of cross-chain transactions
    target = XTXNUM * len(hosts)
    check_procs = []
    val = multiprocessing.Value("i", 0)
    min_init = multiprocessing.Value("d", time.time() * 2)
    max_last_commit = multiprocessing.Value("d", 0)
    latency_sum = multiprocessing.Value("d", 0)
    for idx, host in enumerate(hosts):
        proc = multiprocessing.Process(
            target=check,
            args=(
                idx,
                host,
                val,
                target,
                min_init,
                max_last_commit,
                latency_sum,
            ),
        )
        check_procs.append(proc)
    for proc in check_procs:
        proc.start()
    for proc in check_procs:
        proc.join()

    # Each chain sent XTXNUM transactions, so a total of XTXNUM * CHAINNUM transactions were sent
    assert val.value == target

    # Close relayer
    for rly0, rly1 in relayer_pairs:
        rly0.stop()
        rly1.stop()
    for proc0, proc1 in procs_rly:
        proc0.join()
        proc1.join()
    print("============close relayer!")

    tps = target / (max_last_commit.value - min_init.value)
    print(f"tps: {tps}")
    print("tps ratio: {:.2f}%".format((tps / TPS_0) * 100))
    latency_avg = latency_sum.value / target
    print(f"latency avg: {latency_avg}")


if __name__ == "__main__":
    main()

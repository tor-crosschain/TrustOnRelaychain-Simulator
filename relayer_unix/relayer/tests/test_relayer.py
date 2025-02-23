import math
import time
import requests
import asyncio
import json
import threading
import multiprocessing
from typing import Tuple, List
from tornado.testing import AsyncHTTPTestCase
from chain_simulator.types.transaction import Transaction
from chain_simulator.service.api_service import ApiService
from chain_simulator.blockchain.blockchain import Blockchain
from chain_simulator.mempool.mempool import AsyncMemPool
from chain_simulator.config.config import Config
from relayer.connector.connector import Connector
from relayer.relayer.relayer import Relayer, Mode
from chain_simulator.types.transaction import TranMemo


def pre_test() -> (
    Tuple[
        List[threading.Thread],
        List[threading.Event],
        List[Blockchain],
        List[AsyncMemPool],
        List[ApiService],
        List[str],
    ]
):
    def thread_proxy(cors: List, apiserv: ApiService, stop_api_event: threading.Event):
        """run tornado service in a seperate thread

        :param serv: tornado api service
        :type serv: ApiService
        """

        async def stopapiserv():
            while True:
                if stop_api_event.is_set():
                    break
                await asyncio.sleep(1)
            apiserv.stop_event.set()
            await asyncio.sleep(0.5)

        cors.append(stopapiserv())
     
        asyncio.run(
            asyncio.wait(
                cors,
            )
        )
        print(f"thread-{threading.current_thread().name} stopped!")

    config = Config()
    config.block_size = 20
    config.block_interval = 1
    args1 = {"port": 9001}
    host1 = f"127.0.0.1:{args1['port']}"
    mpool1 = AsyncMemPool(maxsize=config.mempool_size)
    bc1 = Blockchain(pool=mpool1, config=config)
    api_serv1 = ApiService(mpool=mpool1, bc=bc1)
    cors1 = [api_serv1.run_app(args1), bc1.start()]
    stop_api_event1 = threading.Event()
    thread1 = threading.Thread(
        target=thread_proxy, args=(cors1, api_serv1, stop_api_event1)
    )
    thread1.setDaemon(True)
    thread1.start()

    args2 = {"port": 9002}
    host2 = f"127.0.0.1:{args2['port']}"
    mpool2 = AsyncMemPool(maxsize=config.mempool_size)
    bc2 = Blockchain(pool=mpool2, config=config)
    api_serv2 = ApiService(mpool=mpool2, bc=bc2)
    cors2 = [api_serv2.run_app(args2), bc2.start()]
    stop_api_event2 = threading.Event()
    thread2 = threading.Thread(
        target=thread_proxy, args=(cors2, api_serv2, stop_api_event2)
    )
    thread2.setDaemon(True)
    thread2.start()
    time.sleep(1)
    return (
        (thread1, thread2),
        (stop_api_event1, stop_api_event2),
        (bc1, bc2),
        (mpool1, mpool2),
        (api_serv1, api_serv2),
        (host1, host2),
        (cors1, cors2),
    )


def send_tx(host, txnum: int):
    TXNUM = txnum
    datas = [
        {
            "tx": {
                "sender": "send0" + str(x),
                "to": "base",
                "data": json.dumps({"arguments": [f"a{x}", x]}),
                "memo": json.dumps({"type": TranMemo.CTXSRC, "dst": 1}),
            }
        }
        for x in range(TXNUM)
    ]

    url_send_tx = f"http://{host}/send_tx"
    for idx, data in enumerate(datas):
        resp_send_tx = requests.post(url=url_send_tx, data=json.dumps(data), timeout=10)
        assert resp_send_tx.status_code == 200
        resp = json.loads(resp_send_tx.text)
        assert resp["error"] == "", f"response error: {resp['error']}"
        assert resp["code"] == 200, f"response code: {resp['code']}"


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


def set_pre(hosts, pids, classes, bcs: List[Blockchain]):
    for idx, host in enumerate(hosts):
        set_paraid(host, pids[idx])
        set_paratype(host, classes[idx])
        # task_bc = bcs[idx].start()
        # asyncio.run(main=asyncio.wait(
        #         [
        #             task_bc,
        #         ],
        #         timeout=bcs[idx].config.block_interval+1,
        #     ))


def test_set_pre():
    threads, stop_api_events, bcs, mpools, api_servs, hosts, tasks = pre_test()
    set_pre(
        hosts, list(range(len(hosts))), ["Tendermint" for _ in range(len(hosts))], bcs
    )
    while True:
        if mpools[0].empty():
            break
    assert mpools[0].empty()

    for idx, host in enumerate(hosts):
        connector = Connector(host)
        assert connector.pid == idx, f"pid is {connector.pid}"
        assert connector.paratype == "Tendermint", f"paratype is {connector.paratype}"

    bcs[0].stop()
    bcs[1].stop()
    stop_api_events[0].set()
    stop_api_events[1].set()
    threads[0].join()
    threads[1].join()
    assert threads[0].is_alive() is False
    assert threads[1].is_alive() is False


def test_listen():
    threads, stop_api_events, bcs, mpools, api_servs, hosts, tasks = pre_test()
    set_pre(
        hosts, list(range(len(hosts))), ["Tendermint" for _ in range(len(hosts))], bcs
    )

    # send cross-chain transactions to source chain
    # memo = {"type": "SRC-CTX", "dst": 1}
    # wait for source chain to process
    txnum = 60
    send_tx(host=hosts[0], txnum=txnum)
    while True:
        if mpools[0].empty():
            break
    assert mpools[0].empty()
    bcs[0].stop()

    # build relayer
    src_connector = Connector(host=hosts[0], sender="Alice")
    tgt_connector = Connector(host=hosts[1], sender="Bob")
    relayer = Relayer(src_connector, tgt_connector, mode=Mode.MODENOR)

    # relayer starts listening to blocks
    thread_listen = threading.Thread(
        target=relayer.listen_block, args=(src_connector, tgt_connector)
    )
    thread_listen.setDaemon(True)
    thread_listen.start()

    # wait for relayer to listen to all messages
    # check if the number of cross-chain transactions is consistent
    time.sleep(5)
    tx_n = relayer.queue_xtx.qsize()
    assert tx_n == txnum
    bh_n = relayer.queue_header.qsize()
    assert bh_n == bcs[0].block_num
    relayer.stop_listen_block()

    # stop chain2
    bcs[1].stop()
    stop_api_events[0].set()
    stop_api_events[1].set()
    threads[0].join()
    threads[1].join()
    assert threads[0].is_alive() is False
    assert threads[1].is_alive() is False


def test_deal_header():
    # start two chains
    threads, stop_api_events, bcs, mpools, api_servs, hosts, tasks = pre_test()
    set_pre(
        hosts, list(range(len(hosts))), ["Tendermint" for _ in range(len(hosts))], bcs
    )

    # send cross-chain transactions to source chain
    # memo = {"type": "SRC-CTX", "dst": 1}
    # wait for source chain to process
    txnum = 60
    send_tx(host=hosts[0], txnum=txnum)
    while True:
        if mpools[0].empty():
            break
    assert mpools[0].empty()
    bcs[0].stop()  # source chain 停止出块

    # build relayer
    src_connector = Connector(host=hosts[0], sender="Alice")
    tgt_connector = Connector(host=hosts[1], sender="Bob")
    relayer = Relayer(src_connector, tgt_connector, mode=Mode.MODENOR)

    # relayer starts listening to blocks
    thread_listen = threading.Thread(
        target=relayer.listen_block, args=(src_connector, tgt_connector)
    )
    thread_listen.setDaemon(True)
    thread_listen.start()

    # relayer deals with block headers
    thread_header = threading.Thread(
        target=relayer.deal_header, args=(src_connector, tgt_connector)
    )
    thread_header.setDaemon(True)
    thread_header.start()

    # wait for deal_header to synchronize source chain headers to target
    time.sleep(5)
    assert relayer.queue_header.qsize() == 0

    # wait for target chain to process
    while True:
        if mpools[1].empty():
            break
    assert mpools[1].empty()
    bcs[1].stop()  # stop target chain

    # check the total number of transactions on target chain
    dtxa = 0
    for i in range(1, bcs[1].block_num + 1):
        txs = bcs[1].get_block_by_height(i).txs
        dtxa += len(txs)
        for tx in txs:
            print(tx.memo)
            if json.loads(tx.memo)["type"] != TranMemo.CTXHDR:
                dtxa -= 1  # subtract non-block header transactions

    assert bcs[0].block_num == dtxa

    relayer.stop_listen_block()
    relayer.stop_deal_header()
    relayer.stop_deal_xtx()

    bcs[0].stop()
    bcs[1].stop()
    stop_api_events[0].set()
    stop_api_events[1].set()
    threads[0].join()
    threads[1].join()
    assert threads[0].is_alive() is False
    assert threads[1].is_alive() is False


def test_deal_xtx():
    # start two chains
    threads, stop_api_events, bcs, mpools, api_servs, hosts, tasks = pre_test()
    set_pre(
        hosts, list(range(len(hosts))), ["Tendermint" for _ in range(len(hosts))], bcs
    )

    # send cross-chain transactions to source chain
    # memo = {"type": "SRC-CTX", "dst": 1}
    # wait for source chain to process
    txnum = 60
    send_tx(host=hosts[0], txnum=txnum)
    while True:
        if mpools[0].empty():
            break
    assert mpools[0].empty()
    bcs[0].stop()  # stop source chain

    # build relayer
    src_connector = Connector(host=hosts[0], sender="Alice")
    tgt_connector = Connector(host=hosts[1], sender="Bob")
    relayer = Relayer(src_connector, tgt_connector, mode=Mode.MODENOR)

    # relayer starts listening to blocks
    thread_listen = threading.Thread(
        target=relayer.listen_block, args=(src_connector, tgt_connector)
    )
    thread_listen.setDaemon(True)
    thread_listen.start()

    # relayer deals with block headers
    thread_header = threading.Thread(
        target=relayer.deal_header, args=(src_connector, tgt_connector)
    )
    thread_header.setDaemon(True)
    thread_header.start()

    # relayer deals with cross-chain transactions
    thread_xtx = threading.Thread(
        target=relayer.deal_xtx, args=(src_connector, tgt_connector)
    )
    thread_xtx.setDaemon(True)
    thread_xtx.start()

    # wait for deal_header to synchronize source chain headers to target
    time.sleep(10)
    assert relayer.queue_header.qsize() == 0

    # wait for target chain to process
    while not mpools[1].empty() or (
        len(bcs[1].get_block_by_height(bcs[1].block_num).txs) != 0
    ):
        time.sleep(1)
    assert mpools[1].empty()
    assert len(bcs[1].get_block_by_height(bcs[1].block_num).txs) == 0
    bcs[1].stop()  # stop target chain mining

    # check the total number of transactions on target chain
    dtxa = 0
    i = 1
    while True:
        if i > bcs[1].block_num:
            break
        txs = bcs[1].get_block_by_height(i).txs
        dtxa += len(txs)
        for tx in txs:
            print(tx.memo)
            if json.loads(tx.memo)["type"] not in [TranMemo.CTXHDR, TranMemo.CTXDST]:
                dtxa -= 1  # subtract non-block header transactions
        i += 1

    assert bcs[0].block_num + txnum == dtxa

    relayer.stop_listen_block()
    relayer.stop_deal_header()
    relayer.stop_deal_xtx()

    bcs[0].stop()
    bcs[1].stop()
    stop_api_events[0].set()
    stop_api_events[1].set()
    threads[0].join()
    threads[1].join()
    assert threads[0].is_alive() is False
    assert threads[1].is_alive() is False


def test_one_way():
    # start two chains
    threads, stop_api_events, bcs, mpools, api_servs, hosts, tasks = pre_test()
    set_pre(
        hosts, list(range(len(hosts))), ["Tendermint" for _ in range(len(hosts))], bcs
    )

    # send cross-chain transactions to source chain
    # memo = {"type": "SRC-CTX", "dst": 1}
    # wait for source chain to process
    txnum = 60
    send_tx(host=hosts[0], txnum=txnum)
    while True:
        if mpools[0].empty():
            break
    assert mpools[0].empty()
    bcs[0].stop()  # source chain 停止出块

    # build relayer
    src_connector = Connector(host=hosts[0], sender="Alice")
    tgt_connector = Connector(host=hosts[1], sender="Bob")
    relayer = Relayer(src_connector, tgt_connector, mode=Mode.MODENOR)

    process = multiprocessing.Process(target=relayer.start_one_way)
    process.start()
    print(f"one-way process: {process.is_alive()}")

    time.sleep(10)
    assert relayer.queue_header.qsize() == 0

    # wait for target chain to process
    while not mpools[1].empty() or (
        len(bcs[1].get_block_by_height(bcs[1].block_num).txs) != 0
    ):
        time.sleep(1)
    assert mpools[1].empty()
    assert len(bcs[1].get_block_by_height(bcs[1].block_num).txs) == 0
    bcs[1].stop()  

    # check the total number of transactions on target chain
    dtxa = 0
    for i in range(1, bcs[1].block_num + 1):
        txs = bcs[1].get_block_by_height(i).txs
        dtxa += len(txs)
        for tx in txs:
            print(tx.memo)
            if json.loads(tx.memo)["type"] not in [TranMemo.CTXHDR, TranMemo.CTXDST]:
                dtxa -= 1  # subtract non-block header transactions

    assert bcs[0].block_num + txnum == dtxa

    relayer.stop_listen_block()
    relayer.stop_deal_header()
    relayer.stop_deal_xtx()
    process.join()

    bcs[0].stop()
    bcs[1].stop()
    stop_api_events[0].set()
    stop_api_events[1].set()
    threads[0].join()
    threads[1].join()
    assert threads[0].is_alive() is False
    assert threads[1].is_alive() is False


def test_two_way():
    # start two chains
    threads, stop_api_events, bcs, mpools, api_servs, hosts, tasks = pre_test()
    set_pre(
        hosts, list(range(len(hosts))), ["Tendermint" for _ in range(len(hosts))], bcs
    )

    # send cross-chain transactions to source chain
    # memo = {"type": "SRC-CTX", "dst": 1}
    # wait for source chain to process
    txnum = 60
    send_tx(host=hosts[0], txnum=txnum)
    while True:
        if mpools[0].empty():
            break
    assert mpools[0].empty()
    bcs[0].stop()  

    # build relayer
    src_connector = Connector(host=hosts[0], sender="Alice")
    tgt_connector = Connector(host=hosts[1], sender="Bob")
    relayer0 = Relayer(src_connector, tgt_connector, mode=Mode.MODENOR)
    relayer1 = Relayer(tgt_connector, src_connector, mode=Mode.MODENOR)
    process = multiprocessing.Process(
        target=Relayer.start_two_way, args=(relayer0, relayer1)
    )
    process.start()

    time.sleep(10)
    assert relayer0.queue_header.qsize() == 0

    # wait for target chain to process
    while not mpools[1].empty() or (
        len(bcs[1].get_block_by_height(bcs[1].block_num).txs) != 0
    ):
        time.sleep(1)
    assert mpools[1].empty()
    assert len(bcs[1].get_block_by_height(bcs[1].block_num).txs) == 0
    bcs[1].stop() 

    # check the total number of transactions on target chain
    dtxa = 0
    for i in range(1, bcs[1].block_num + 1):
        txs = bcs[1].get_block_by_height(i).txs
        dtxa += len(txs)
        for tx in txs:
            print(tx.memo)
            if json.loads(tx.memo)["type"] not in [TranMemo.CTXHDR, TranMemo.CTXDST]:
                dtxa -= 1  # subtract non-block header transactions

    assert bcs[0].block_num + txnum == dtxa

    relayer0.stop_listen_block()
    relayer0.stop_deal_header()
    relayer0.stop_deal_xtx()
    relayer1.stop_listen_block()
    relayer1.stop_deal_header()
    relayer1.stop_deal_xtx()
    process.join()

    bcs[0].stop()
    bcs[1].stop()
    stop_api_events[0].set()
    stop_api_events[1].set()
    threads[0].join()
    threads[1].join()
    assert threads[0].is_alive() is False
    assert threads[1].is_alive() is False

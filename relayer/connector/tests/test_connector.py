import math
import time
import requests
import asyncio
import json
import multiprocessing
import threading
from typing import Tuple, List
from relayer.connector.connector import Connector
from tornado.testing import AsyncHTTPTestCase
from chain_simulator.types.transaction import Transaction
from chain_simulator.service.api_service import ApiService
from chain_simulator.blockchain.blockchain import Blockchain
from chain_simulator.mempool.mempool import AsyncMemPool
from chain_simulator.config.config import Config


def pre_test() -> Tuple[threading.Thread, Blockchain, AsyncMemPool, ApiService]:
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
    args = {"port": 8888}
    host = f"127.0.0.1:{args['port']}"
    mpool = AsyncMemPool(maxsize=config.mempool_size)
    bc = Blockchain(pool=mpool, config=config)
    api_serv = ApiService(mpool=mpool, bc=bc)
    cors = [api_serv.run_app(args), bc.start()]
    stop_api_event = threading.Event()
    thread = threading.Thread(
        target=thread_proxy, args=(cors, api_serv, stop_api_event)
    )
    thread.setDaemon(True)
    thread.start()

    time.sleep(1)
    return (
        thread,
        stop_api_event,
        bc,
        mpool,
        api_serv,
        host,
        cors,
    )


def pre_test2() -> Tuple[threading.Thread, Blockchain, AsyncMemPool, ApiService]:
    def thread_proxy(serv: ApiService):
        """run tornado service in a seperate thread

        :param serv: tornado api service
        :type serv: ApiService
        """
        asyncio.run(
            asyncio.wait(
                [serv.run_app(None)],
                return_when="FIRST_COMPLETED",
            )
        )

    config = Config()
    mpool = AsyncMemPool(maxsize=config.mempool_size)
    bc = Blockchain(pool=mpool, config=config)
    api_serv = ApiService(mpool=mpool, bc=bc)
    thread = threading.Thread(target=thread_proxy, args=(api_serv,))
    thread.start()
    time.sleep(1)

    TXNUM = 40
    datas = [
        {
            "tx": {
                "sender": "send0" + str(x),
                "to": "base",
                "data": json.dumps({"arguments": [f"a{x}", x, f"b{x}", x + 1]}),
                "memo": json.dumps({"type": ""}),
            }
        }
        for x in range(TXNUM)
    ]
    url_send_tx = "http://127.0.0.1:8888/send_tx"
    for idx, data in enumerate(datas):
        resp_send_tx = requests.post(url=url_send_tx, data=json.dumps(data), timeout=10)
        assert resp_send_tx.status_code == 200
        resp = json.loads(resp_send_tx.text)
        assert resp["error"] == "", f"response error: {resp['error']}"
        assert resp["code"] == 200, f"response code: {resp['code']}"
    assert mpool.size() == TXNUM

    bc.config.block_size = 20
    bc.config.block_interval = 1
    block_num_expected = math.ceil(len(datas) / bc.config.block_size)
    task_bc = bc.start()
    cost_expected = bc.config.block_interval * (block_num_expected + 1)
    print(f"cost_expected:{cost_expected}")

    asyncio.run(
        main=asyncio.wait(
            [
                task_bc,
            ],
            timeout=cost_expected,
        )
    )

    return thread, bc, mpool, api_serv


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
        task_bc = bcs[idx].start()
        asyncio.run(
            main=asyncio.wait(
                [
                    task_bc,
                ],
                timeout=bcs[idx].config.block_interval + 1,
            )
        )


def test_set_pre():
    (
        thread_server,
        stop_api_event,
        blockchain,
        mempool,
        api_serv,
        host,
        cors,
    ) = pre_test()
    host = "127.0.0.1:8888"
    set_pre([host], [1], ["Tendermint"], [blockchain])
    connector = Connector(host=host, sender="Alice")
    assert connector.pid == 1, f"pid is {connector.pid}"
    assert connector.paratype == "Tendermint", f"pid is {connector.paratype}"

    blockchain.stop()
    stop_api_event.set()
    thread_server.join()
    assert thread_server.is_alive() is False


def test_query_block():
    (
        thread_server,
        stop_api_event,
        blockchain,
        mempool,
        api_serv,
        host,
        cors,
    ) = pre_test()
    host = "127.0.0.1:8888"
    set_pre([host], [1], ["Tendermint"], [blockchain])
    connector = Connector(host=host, sender="Alice")
    blknum = blockchain.block_num
    for i in range(1, blknum + 1):
        block = connector.query_block(i)
        assert block.height == i

    blockchain.stop()
    stop_api_event.set()
    thread_server.join()
    assert thread_server.is_alive() is False


def test_query_max_xbn():
    (
        thread_server,
        stop_api_event,
        blockchain,
        mempool,
        api_serv,
        host,
        cors,
    ) = pre_test()
    host = "127.0.0.1:8888"
    set_pre([host], [1], ["Tendermint"], [blockchain])
    connector = Connector(host=host, sender="Alice")
    maxnum = connector.query_max_xbn(pid=0)
    assert maxnum == 0

    blockchain.stop()
    stop_api_event.set()
    thread_server.join()
    assert thread_server.is_alive() is False


def test_query_xtx_proof():
    (
        thread_server,
        stop_api_event,
        blockchain,
        mempool,
        api_serv,
        host,
        cors,
    ) = pre_test()
    host = "127.0.0.1:8888"
    set_pre([host], [1], ["Tendermint"], [blockchain])
    connector = Connector(host=host, sender="Alice")
    blknum = blockchain.block_num
    for i in range(1, blknum + 1):
        block = connector.query_block(i)
        assert block.height == i
        for tx in block.txs:
            tp = connector.query_xtx_proof(tx)
            assert tp == tx.hash().hex()

    blockchain.stop()
    stop_api_event.set()
    thread_server.join()
    assert thread_server.is_alive() is False


def test_query_xtx_receipt_proof():
    (
        thread_server,
        stop_api_event,
        blockchain,
        mempool,
        api_serv,
        host,
        cors,
    ) = pre_test()
    host = "127.0.0.1:8888"
    set_pre([host], [1], ["Tendermint"], [blockchain])
    connector = Connector(host=host, sender="Alice")
    blknum = blockchain.block_num
    for i in range(1, blknum + 1):
        block = connector.query_block(i)
        assert block.height == i
        for tx in block.txs:
            tp = connector.query_xtx_receipt_proof(tx)
            assert tp == tx.hash().hex()

    blockchain.stop()
    stop_api_event.set()
    thread_server.join()
    assert thread_server.is_alive() is False


def test_send_tx():
    (
        thread_server,
        stop_api_event,
        blockchain,
        mempool,
        api_serv,
        host,
        cors,
    ) = pre_test()
    host = "127.0.0.1:8888"
    set_pre([host], [1], ["Tendermint"], [blockchain])
    connector = Connector(host=host, sender="Alice")
    TXNUM = 40
    datas = [
        {
            "tx": {
                "sender": "send0" + str(x),
                "to": "base",
                "data": json.dumps({"arguments": [f"a{x}", x, f"b{x}", x + 1]}),
                "memo": json.dumps({"type": ""}),
            }
        }
        for x in range(TXNUM)
    ]
    for txj in datas:
        tx = Transaction.from_json(txj["tx"])
        resp = connector.send_tx(tx)
        assert resp == tx.hash().hex()

    assert mempool.size() == TXNUM

    blockchain.stop()
    stop_api_event.set()
    thread_server.join()
    assert thread_server.is_alive() is False

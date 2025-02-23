import json
import time
import pickle
import urllib.parse
import asyncio
from typing import Coroutine
from chain_simulator.service.api_service import ApiService
from chain_simulator.blockchain.blockchain import Blockchain
from chain_simulator.mempool.mempool import AsyncMemPool
from chain_simulator.config.config import Config
from chain_simulator.types.transaction import Transaction, TxStatus
from tornado.testing import AsyncHTTPTestCase


class TestApiServiceApp(AsyncHTTPTestCase):
    def __init__(self, methodName: str = "runTest") -> None:
        super().__init__(methodName)

    def get_app(self):
        config = Config()
        self.mpool = AsyncMemPool(maxsize=config.mempool_size)
        self.bc = Blockchain(pool=self.mpool, config=config)
        api_serv = ApiService(mpool=self.mpool, bc=self.bc)
        return api_serv.make_app()

    def test_send_tx(self):
        datas = [
            {
                "tx": {
                    "sender": "send0" + str(x),
                    "to": "base",
                    "data": json.dumps({"arguments": [f"a{x}", x, f"b{x}", x + 1]}),
                    "memo": json.dumps({"type": ""}),
                }
            }
            for x in range(40)
        ]

        for idx, data in enumerate(datas):
            resp_send_tx = self.fetch("/send_tx", method="POST", body=json.dumps(data))
            txt_0 = json.loads(resp_send_tx.body.decode())
            tx = Transaction.from_json(data["tx"])
            self.assertEqual(resp_send_tx.code, 200)
            self.assertEqual(txt_0["msg"], tx.hash().hex())
            self.assertEqual(txt_0["code"], 200)
            self.assertEqual(txt_0["error"], "")
            self.assertEqual(self.mpool.size(), idx + 1)

        self.bc.config.block_size = 20
        self.bc.config.block_interval = 1
        block_num_expected = len(datas) / self.bc.config.block_size
        task_bc = self.bc.start()
        cost_expected = self.bc.config.block_interval * (block_num_expected + 1)
        print(f"cost_expected:{cost_expected}")

        asyncio.run(
            main=asyncio.wait(
                [
                    task_bc,
                ],
                timeout=cost_expected,
            )
        )

        self.assertEqual(self.bc.blocks[-1].height, block_num_expected)

    def test_query_tx(self):
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
        txhashes = []
        for idx, data in enumerate(datas):
            resp_send_tx = self.fetch("/send_tx", method="POST", body=json.dumps(data))
            txt = json.loads(resp_send_tx.body.decode())
            self.assertNotEqual(txt["msg"], "")
            txhash = txt["msg"]
            txhashes.append(txhash)
        self.bc.config.block_size = 20
        self.bc.config.block_interval = 1
        block_num_expected = len(datas) / self.bc.config.block_size
        task_bc = self.bc.start()
        cost_expected = self.bc.config.block_interval * (block_num_expected + 1)
        asyncio.run(
            main=asyncio.wait(
                [
                    task_bc,
                ],
                timeout=cost_expected,
            )
        )

        # query tx
        for txhash in txhashes:
            resp = self.fetch(f"/query_tx?txhash={txhash}", method="GET")
            resprawdata = resp.body.decode()
            self.assertNotEqual(resprawdata, "")
            txt = json.loads(resprawdata)
            self.assertEqual(txt["error"], "")
            self.assertNotEqual(txt["msg"], "")
            txjson = json.loads(txt["msg"])
            tx = Transaction.from_json(txjson)
            self.assertNotEqual(tx.height, 0)

        # query state
        toctr = "base"
        for i in range(TXNUM):
            data = urllib.parse.quote(json.dumps({"arguments": [f"a{i}"]}))
            print(f"data: {data}")
            resp = self.fetch(f"/call?to={toctr}&data={data}", method="GET")
            print(f"resp.effective_url:{resp.effective_url}")
            print(f"resp.code: {resp.code}")
            resprawdata = resp.body.decode()
            self.assertNotEqual(resprawdata, "")
            txt = json.loads(resprawdata)
            self.assertEqual(txt["error"], "")
            self.assertNotEqual(txt["msg"], "")
            res = json.loads(txt["msg"])
            self.assertEqual(res["code"], 1)
            self.assertEqual(res["out"], f"['{i}']")

    def test_ctr(self):
        TXNUM = 40

        self.bc.config.block_size = 20
        self.bc.config.block_interval = 1
        block_num_expected = TXNUM / self.bc.config.block_size
        task_bc = self.bc.start()
        cost_expected = self.bc.config.block_interval * (block_num_expected + 1)

        # deploy ctr
        from chain_simulator.vm.tests.codes.code_add import CodeAdd

        code_add = CodeAdd()
        ctr = pickle.dumps(code_add).hex()
        data_ctr = {
            "tx": {
                "sender": "send0",
                "to": "",
                "data": ctr,
                "memo": json.dumps({"type": ""}),
            }
        }
        resp_deploy = self.fetch("/send_tx", method="POST", body=json.dumps(data_ctr))
        txt_deploy = json.loads(resp_deploy.body.decode())
        self.assertNotEqual(txt_deploy["msg"], "")
        txhash_deploy = txt_deploy["msg"]
        # start consensus
        asyncio.run(
            main=asyncio.wait(
                [
                    task_bc,
                ],
                timeout=2,
            )
        )
        # query ctr hash
        ctraddr = None
        starttime = time.time()
        while time.time() - starttime < 10:
            resp = self.fetch(f"/query_tx?txhash={txhash_deploy}", method="GET")
            txt = json.loads(resp.body.decode())
            if txt["code"] != 200:
                time.sleep(1)
                continue
            txjson = json.loads(txt["msg"])
            tx = Transaction.from_json(txjson)
            ctraddr = tx.out
        self.assertIsNotNone(ctraddr)

        # execute contracts
        datas = [
            {
                "tx": {
                    "sender": "send0" + str(x),
                    "to": ctraddr,
                    "data": json.dumps({"func": "add", "arguments": [f"a", x]}),
                    "memo": json.dumps({"type": ""}),
                }
            }
            for x in range(TXNUM)
        ]
        txhashes = []
        for idx, data in enumerate(datas):
            resp_send_tx = self.fetch("/send_tx", method="POST", body=json.dumps(data))
            txt = json.loads(resp_send_tx.body.decode())
            self.assertNotEqual(txt["msg"], "")
            txhash = txt["msg"]
            txhashes.append(txhash)
        # start consensus
        task_bc = self.bc.start()
        asyncio.run(
            main=asyncio.wait(
                [
                    task_bc,
                ],
                timeout=cost_expected,
            )
        )

        # query state
        sum = 10
        for i in range(TXNUM):
            sum += i 
        toctr = ctraddr
        data = urllib.parse.quote(json.dumps({"arguments": [f"a"]}))
        print(f"data: {data}")
        resp = self.fetch(f"/call?to={toctr}&data={data}", method="GET")
        print(f"resp.effective_url:{resp.effective_url}")
        print(f"resp.code: {resp.code}")
        resprawdata = resp.body.decode()
        self.assertNotEqual(resprawdata, "")
        txt = json.loads(resprawdata)
        self.assertEqual(txt["error"], "")
        self.assertNotEqual(txt["msg"], "")
        res = json.loads(txt["msg"])
        self.assertEqual(res["code"], 1)
        self.assertEqual(res["out"], f"['{sum}']")

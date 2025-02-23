import json
import asyncio
import math
import requests
import tornado
import threading
from typing import Coroutine
from chain_simulator.service.api_service import ApiService
from chain_simulator.blockchain.blockchain import Blockchain
from chain_simulator.mempool.mempool import AsyncMemPool
from chain_simulator.config.config import Config
from chain_simulator.types.transaction import Transaction, TxStatus
from chain_simulator.types.block import Block
from tornado.testing import AsyncHTTPTestCase, gen_test


class TestApiServiceBlockchainHandler(AsyncHTTPTestCase):
    def __init__(self, methodName: str = "runTest") -> None:
        super().__init__(methodName)

    def get_app(self):
        config = Config()
        self.mpool = AsyncMemPool(maxsize=config.mempool_size)
        self.bc = Blockchain(pool=self.mpool, config=config)
        api_serv = ApiService(mpool=self.mpool, bc=self.bc)
        return api_serv.make_app()

    def test_query_block(self):
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

        for idx, data in enumerate(datas):
            resp_send_tx = self.fetch("/send_tx", method="POST", body=json.dumps(data))
            self.assertEqual(resp_send_tx.code, 200)

        self.bc.config.block_size = 20
        self.bc.config.block_interval = 1
        block_num_expected = math.ceil(len(datas) / self.bc.config.block_size)
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

        for i in range(1, block_num_expected + 1):
            resp_blk = self.fetch(f"/query_block?bn={i}", method="GET")
            self.assertEqual(resp_blk.code, 200)
            resp = json.loads(resp_blk.body.decode())
            self.assertEqual(resp["error"], "")
            self.assertEqual(resp["code"], 200)
            blk: dict = json.loads(resp["msg"])
            self.assertEqual(blk["height"], i)
            block = Block.from_json(blk)
            self.assertEqual(block.height, i)

    def test_query_tx_proof(self):
        tx = Transaction()
        txhash = tx.hash().hex()
        resp_tp = self.fetch(f"/query_tx_proof?txhash={txhash}", method="GET")
        self.assertEqual(resp_tp.code, 200)
        resp = json.loads(resp_tp.body.decode())
        self.assertEqual(resp["error"], "")
        self.assertEqual(resp["code"], 200)
        proof: str = resp["msg"]
        self.assertEqual(proof, txhash)

    def test_query_tx_receipt_proof(self):
        tx = Transaction()
        txhash = tx.hash().hex()
        resp_trp = self.fetch(f"/query_tx_receipt_proof?txhash={txhash}", method="GET")
        self.assertEqual(resp_trp.code, 200)
        resp = json.loads(resp_trp.body.decode())
        self.assertEqual(resp["error"], "")
        self.assertEqual(resp["code"], 200)
        proof: str = resp["msg"]
        self.assertEqual(proof, txhash)

    def test_query_block_number(self):
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

        for idx, data in enumerate(datas):
            resp_send_tx = self.fetch("/send_tx", method="POST", body=json.dumps(data))
            self.assertEqual(resp_send_tx.code, 200)

        self.bc.config.block_size = 20
        self.bc.config.block_interval = 1
        block_num_expected = math.ceil(len(datas) / self.bc.config.block_size)
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
        resp_blk = self.fetch(f"/query_block_number", method="GET")
        self.assertEqual(resp_blk.code, 200)
        resp = json.loads(resp_blk.body.decode())
        self.assertEqual(resp["error"], "")
        self.assertEqual(resp["code"], 200)
        bn = resp["msg"]
        self.assertEqual(bn, str(block_num_expected))

    def test_query_pool_count(self):
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

        for idx, data in enumerate(datas):
            resp_send_tx = self.fetch("/send_tx", method="POST", body=json.dumps(data))

        res = self.fetch("/query_pool_count", method="GET")
        response = json.loads(res.body.decode())
        assert response["msg"] == "40"

    def test_start_stop_mining(self):
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

        for idx, data in enumerate(datas):
            resp_send_tx = self.fetch("/send_tx", method="POST", body=json.dumps(data))
            self.assertEqual(resp_send_tx.code, 200)

        self.bc.config.block_size = 20
        self.bc.config.block_interval = 1

        async def control():
            await asyncio.sleep(self.bc.config.block_interval)
            res = await self.http_client.fetch(
                self.get_url("/stop_mining"), method="POST", body=json.dumps(data)
            )
            print(f"res: {res.code}")
            start_num = self.bc.block_num
            await asyncio.sleep(self.bc.config.block_interval * 2)
            end_num = self.bc.block_num
            assert (
                start_num == end_num or start_num + 1 == end_num
            ), f"start_num is {start_num}, end_num is {end_num} "
            self.bc.stop()
            await asyncio.sleep(1)

        async def main():
            res = await asyncio.gather(*[self.bc.start(), control()])
            print(res)

        self.io_loop.run_sync(main)

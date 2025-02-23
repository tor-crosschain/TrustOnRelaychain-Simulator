from __future__ import annotations
import urllib.parse
import json
import time
import asyncio
from typing import List, Dict
from chain_simulator.types.block import Block
from chain_simulator.types.transaction import Transaction
from unix_server.client.client_ms import ClientMS
from chain_simulator.service_unix.tool.response import StandardResponse
from chain_simulator.vm.executor import Response as ExecutorResponse


class ConnectorUnix(object):
    def __init__(
        self,
        socket_paths: List[str],
        sender: str = "default",
        to: str = "lightclient",  
        isinter: bool = False,  
    ) -> None:
        """
        """
        assert isinstance(isinter, bool)
        self.socket_paths = socket_paths
        self.client = ClientMS(socket_paths=socket_paths)
        self.sender = sender
        self.to = to
        self.isinter = isinter
        self.paratype = None
        self.pid = None
    
    def close(self):
        self.client.close()

    @staticmethod
    async def new(
        socket_paths: List[str],
        sender: str = "default",
        to: str = "lightclient", 
        isinter: bool = False, 
    ):
        self = ConnectorUnix(socket_paths, sender, to, isinter)
        # get the type and id of the chain from the light client
        self.paratype = await self.__get_paratype()
        self.pid = await self.__get_paraid()
        return self

    async def __req(self, url: str, params: Dict) -> str:
        resp = self.client.get(url, params)
        assert resp.code == 200, f"code error: {resp.err}"
        res = StandardResponse.from_str(resp.msg)
        assert res.code == 200, f"code error: {res.error}"
        return res.msg

    async def __get_paratype(self) -> str:
        """get the type of the chain from the light client contract"""
        url = "/call"
        data = urllib.parse.quote(json.dumps({"func": "query_paratype"}))
        params = {"to": self.to, "data": data}
        msg = await self.__req(url, params)
        resp = ExecutorResponse.from_str(msg)
        assert resp.code == 1, f"code error: {msg}"
        return resp.out

    async def __get_paraid(self) -> int:
        """get the id of the chain from the light client contract
        Returns:
            int: chain id
        """
        url = f"/call"
        data = urllib.parse.quote(json.dumps({"func": "query_paraid"}))
        params = {"to": self.to, "data": data}
        msg = await self.__req(url, params)
        resp = ExecutorResponse.from_str(msg)
        assert resp.code == 1, f"code error: {msg}"
        return int(resp.out)

    def send(self):
        pass

    def query(self):
        pass

    async def query_block_number(self) -> int:
        url = f"/query_block_number"
        msg = await self.__req(url, {})
        bn = int(msg)
        return bn

    async def query_header_cs_height(self, pid: int, height: int) -> int:
        """for the chain identified as pid, query the confirmed block height of the block at height in the lightclient contract of the chain

        :param pid: the id of the chain to be queried
        :type pid: int
        :param height: the height of the block to be queried
        :type height: int
        :rtype: int
        """
        out = await self.query_synced_header(pid, height)
        cs_height = int(out["cs_height"])
        return cs_height

    async def query_synced_header(self, pid: int, height: int) -> dict:
        """for the chain identified as pid, query the block header at height in the lightclient contract of the chain
        the returned block header is in the json format
        {
            'header': '',
            'height': 0
        }

        :param pid: the id of the chain to be queried
        :type pid: int
        :param height: the height of the block to be queried
        :type height: int
        :rtype: str
        """
        url = f"/call"
        data = urllib.parse.quote(
            json.dumps({"func": "query_header", "arguments": [pid, height]})
        )
        params = {"to": self.to, "data": data}
        msg = await self.__req(url, params)
        resp = ExecutorResponse.from_str(msg)
        assert resp.code == 1, f"query failed! response: {msg}"
        header = json.loads(resp.out)
        return header

    async def query_max_xbn(self, pid: int) -> int:
        """
        query max synchronized block num on dest chain
        pid: str. idx of parachain
        """
        # data = urllib.parse.quote(json.dumps({"arguments": [f"a"]}))
        # print(f"data: {data}")
        # resp = self.fetch(f"/call?to={toctr}&data={data}", method="GET")
        url = f"/call"
        data = urllib.parse.quote(
            json.dumps({"func": "query_header_maxn", "arguments": [pid]})
        )
        params = {"to": self.to, "data": data}
        msg = await self.__req(url, params)
        resp = ExecutorResponse.from_str(msg)
        assert resp.code == 1, f"execute failed! response: {msg}"
        out = int(resp.out)
        return out

    async def query_block(self, bn: int) -> Block:
        """query block by block number from blockchain

        :param bn: block number
        :type bn: int
        :return: block numbered bn
        :rtype: Block
        """
        url = f"/query_block"
        params = {"bn": bn}
        msg = await self.__req(url, params)
        block = Block.from_str(msg)
        return block

    async def query_xtx_proof(self, xtx: Transaction) -> str:
        """query transaction proof(existence) of xtx from blockchain

        :param xtx: crosschain transaction
        :type xtx: Transaction
        :return: transaction proof of xtx, type of proof is hexStr
        :rtype: str
        """
        xtxhash = xtx.hash().hex()
        url = f"/query_tx_proof"
        params = {"txhash": xtxhash}
        msg = await self.__req(url, params)
        return msg

    async def query_xtx_receipt_proof(self, xtx: Transaction) -> str:
        """query receipt proof(existence) of xtx from blockchain

        :param xtx: crosschain transaction
        :type xtx: Transaction
        :return: receipt proof of xtx, is converted from bytes to str
        :rtype: str
        """
        xtxhash = xtx.hash().hex()
        url = f"/query_tx_receipt_proof"
        params = {"txhash": xtxhash}
        msg = await self.__req(url, params)
        return msg

    def build_tx(self, data: str, memo: str) -> Transaction:
        """construct a transaction

        :param data: the data of the transaction
        :type data: str
        :param memo: the memo of the transaction
        :type memo: str
        :return: the transaction structure
        :rtype: Transaction
        """
        return Transaction(sender=self.sender, to=self.to, memo=memo, data=data)

    async def send_tx(self, tx: Transaction) -> str:
        """send tx to blockchain

        :param tx: tx to be sent
        :type tx: Transaction
        :return: result from api:send_tx
        :rtype: str
        """
        url = f"/send_tx"
        data = {"tx": tx.as_json()}
        msg = await self.__req(url, data)
        return msg

    async def query_tx(self, txhash: str) -> str:
        url = f"/query_tx"
        params = {"txhash": txhash}  # post data must be hexstr
        msg = await self.__req(url, params)
        return msg

    async def wait_tx(self, txhash: str, timeout=300) -> Transaction:
        starttime = time.time()
        tx = None
        while True:
            if time.time() - starttime > timeout:
                raise Exception(f"wait txhash({txhash}) timeout!")
            try:
                tx = self.query_tx(txhash)
                break
            except Exception as e:
                print(f"wait tx({txhash}) warning: {str(e)}")
                asyncio.sleep(1)
        if tx is not None:
            tx = json.loads(tx)
            return Transaction.from_json(tx)
        else:
            raise Exception(f"wait txhash({txhash}) return None!")

    async def query_uv_exists(self, height: int) -> bool:
        """
        query uv tx exists
        """
        assert isinstance(height, int), "height must be int"
        url = f"/call"
        data = urllib.parse.quote(
            json.dumps(
                {
                    "func": "query_uv_exists",
                    "arguments": [
                        height,
                    ],
                }
            )
        )
        params = {"to": self.to, "data": data}
        msg = await self.__req(url, params)
        resp = ExecutorResponse.from_str(msg)
        assert resp.code == 1, f"execute failed! response: {resp.out}"
        out = resp.out
        return out == "1"

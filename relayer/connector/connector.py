import requests
import urllib.parse
import json
import time
import typing
from chain_simulator.types.block import Block
from chain_simulator.types.transaction import Transaction


class Connector(object):
    def __init__(
        self,
        host: str,
        sender: str = "default",
        to: str = "lightclient",
        isinter: bool = False,
        para_type: typing.Optional[str] = None,
        para_id: typing.Optional[int] = None,
    ) -> None:
        """Connector init

        :param pid: id of parallel chain
        :type pid: int
        :param paratype: type of parallel chain, such as 'Ethereum', 'Tendermint', ...
        :type paratype: str
        :param host: rpc of parallel chain
        :type host: str
        :param sender: sender of relayer with this connector,
            defaults to "default"
        :type sender: str, optional
        :param to: to of relayer with this connector,
            defaults to "lightclient" referred to cross light client contract
        :type to: str, optional
        :param inter: whether it is to inter chain
        :type inter: bool, optional, default to False
        """
        assert isinstance(isinter, bool)
        self.host = host
        self.sender = sender
        self.to = to
        self.isinter = isinter
        self.paratype = para_type if para_type is not None else self.__get_paratype()
        self.pid = para_id if para_id is not None else self.__get_paraid()

    def __req(self, url: str, params: dict, method: str = "GET") -> dict:
        assert method in ["GET", "POST"], f"invalid method: {method}"
        headers = {"Connection": "close"}
        for _ in range(3):

            try:
                if method == "GET":
                    res = requests.get(url, params=params, headers=headers)
                else:
                    res = requests.post(url, data=params, headers=headers)
            except Exception as e:
                print(f"req_get failed: {str(e)}, retry after 1s, url: {url}")
                time.sleep(1)
                continue

            assert (
                res.status_code == 200
            ), f"response status_code: {res.status_code}, msg: {res.text}"
            resp = json.loads(res.text)
            assert resp["error"] == "", f"response error: {resp['error']}"
            assert resp["code"] == 200, f"response code: {resp['code']}"
            return resp

    def __get_paratype(self) -> str:
        """Get the type of the chain from the light client contract"""
        url = f"http://{self.host}/call"
        data = urllib.parse.quote(json.dumps({"func": "query_paratype"}))
        params = {"to": self.to, "data": data}
        resp = self.__req(url=url, params=params)
        res = json.loads(resp["msg"])
        assert res["code"] == 1, f"code error: {resp['msg']}"
        out = res["out"]
        return out

    def __get_paraid(self) -> int:
        """Get the identifier of the chain from the light client contract

        Returns:
            int: chain identifier
        """
        url = f"http://{self.host}/call"
        data = urllib.parse.quote(json.dumps({"func": "query_paraid"}))
        params = {"to": self.to, "data": data}
        resp = self.__req(url=url, params=params)
        res = json.loads(resp["msg"])
        assert res["code"] == 1, f"code error: {resp['msg']}"
        out = int(res["out"])
        return out

    def send(self):
        pass

    def query(self):
        pass

    def query_block_number(self) -> int:
        url = f"http://{self.host}/query_block_number"
        resp = self.__req(url=url, params=None)
        bn = int(resp["msg"])
        return bn

    def query_header_cs_height(self, pid: int, height: int) -> int:
        """For the block header with the specified pid and height in the light client contract of that chain, query the confirmed block height on the current chain.

        :param pid: The identifier of the blockchain to query
        :type pid: int
        :param height: The block height to query
        :type height: int
        :rtype: int
        """
        out = self.query_synced_header(pid, height)
        cs_height = int(out["cs_height"])
        return cs_height

    def query_synced_header(self, pid: int, height: int) -> dict:
        """For the block header with the specified pid and height in the light client contract of that chain, query the block header.
        The returned block header is in json format:
        {
            'header': '',
            'height': 0
        }

        :param pid: The identifier of the blockchain to query
        :type pid: int
        :param height: The block height to query
        :type height: int
        :rtype: str
        """
        url = f"http://{self.host}/call"
        data = urllib.parse.quote(
            json.dumps({"func": "query_header", "arguments": [pid, height]})
        )
        params = {"to": self.to, "data": data}
        resp = self.__req(url=url, params=params)
        res = json.loads(resp["msg"])
        if res["code"] != 1:
            return {}
        out = json.loads(res["out"])
        return out

    def query_max_xbn(self, pid: int) -> int:
        """
        query max synchronized block num on dest chain
        pid: str. idx of parachain
        """
        # data = urllib.parse.quote(json.dumps({"arguments": [f"a"]}))
        # print(f"data: {data}")
        # resp = self.fetch(f"/call?to={toctr}&data={data}", method="GET")
        url = f"http://{self.host}/call"
        data = urllib.parse.quote(
            json.dumps({"func": "query_header_maxn", "arguments": [pid]})
        )
        params = {"to": self.to, "data": data}
        resp = self.__req(url=url, params=params)
        res = json.loads(resp["msg"])
        assert res["code"] == 1, f"execution failed! error: {res['out']}"
        out = int(res["out"])
        return out

    def query_block(self, bn: int) -> Block:
        """query block by block number from blockchain

        :param bn: block number
        :type bn: int
        :return: block numbered bn
        :rtype: Block
        """
        url = f"http://{self.host}/query_block"
        params = {"bn": bn}
        resp = self.__req(url=url, params=params)
        blk = json.loads(resp["msg"])
        block = Block.from_json(blk)
        return block

    def query_xtx_proof(self, xtx: Transaction) -> str:
        """query transaction proof(existence) of xtx from blockchain

        :param xtx: crosschain transaction
        :type xtx: Transaction
        :return: transaction proof of xtx, type of proof is hexStr
        :rtype: str
        """
        xtxhash = xtx.hash().hex()
        url = f"http://{self.host}/query_tx_proof"
        params = {"txhash": xtxhash}
        resp = self.__req(url=url, params=params)
        proof = resp["msg"]
        return proof

    def query_xtx_receipt_proof(self, xtx: Transaction) -> str:
        """query receipt proof(existence) of xtx from blockchain

        :param xtx: crosschain transaction
        :type xtx: Transaction
        :return: receipt proof of xtx, is converted from bytes to str
        :rtype: str
        """
        xtxhash = xtx.hash().hex()
        url = f"http://{self.host}/query_tx_receipt_proof"
        params = {"txhash": xtxhash}
        resp = self.__req(url=url, params=params)
        proof = resp["msg"]
        return proof

    def build_tx(self, data: str, memo: str) -> Transaction:
        """Build transaction

        :param data: transaction data body
        :type data: str
        :param memo: transaction memo
        :type memo: str
        :return: transaction structure
        :rtype: Transaction
        """
        return Transaction(sender=self.sender, to=self.to, memo=memo, data=data)

    def send_tx(self, tx: Transaction) -> str:
        """send tx to blockchain

        :param tx: tx to be sent
        :type tx: Transaction
        :return: result from api:send_tx
        :rtype: str
        """
        url = f"http://{self.host}/send_tx"
        data = json.dumps({"tx": tx.as_json()})  # post data must be str
        resp = self.__req(url=url, params=data, method="POST")
        result = resp["msg"]
        return result

    def query_tx(self, txhash: str) -> str:
        url = f"http://{self.host}/query_tx"
        params = {"txhash": txhash}  # post data must be hexstr
        resp = self.__req(url=url, params=params)
        result = resp["msg"]
        return result

    def wait_tx(self, txhash: str, timeout=300) -> Transaction:
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
                time.sleep(1)
        if tx is not None:
            tx = json.loads(tx)
            return Transaction.from_json(tx)
        else:
            raise Exception(f"wait txhash({txhash}) return None!")

    def query_uv_exists(self, height: int) -> bool:
        """
        query uv tx exists
        """
        assert isinstance(height, int), "height must be int"
        url = f"http://{self.host}/call"
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
        resp = self.__req(url=url, params=params)
        res = json.loads(resp["msg"])
        assert res["code"] == 1, f"execution failed! error: {res['out']}"
        out = res["out"]
        return out == "1"

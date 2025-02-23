import urllib.parse
import json
from typing import List, Dict, Callable
from chain_simulator.blockchain.blockchain_p import BlockchainStates
from chain_simulator.types.transaction import Transaction, TxStatus
from chain_simulator.service_unix.tool.response import StandardResponse
from unix_server.server.server import Handler

class TransactionHandler(Handler):
    """
    send_tx: POST. receive a transaction
        args:
            msg: str. a str which could be decoded by json
    query_tx: GET. query a tx
        args:
            hash[optional]: str.
            sender[optional]: str.
            memo[optional]: str
    """

    def initialize(self, bcstates: BlockchainStates, **kwargs) -> None:
        self.bcstates = bcstates
        self.kwargs = kwargs

    @classmethod
    def routers(cls) -> Dict:
        routers = {
            r"/send_tx": cls.send_tx,
            r"/query_tx": cls.query_tx,
            r"/call": cls.call_ctr,
        }
        return routers

    def get(self):
        resp = StandardResponse()
        try:
            callfunc: callable = self.__get_func()
            result = callfunc(self)
            resp.set_code(200).set_msg(str(result))
        except Exception as e:
            resp.set_code(201).set_error(str(e))
        finally:
            self.write(resp.as_str())

    def post(self):
        resp = StandardResponse()
        try:
            callfunc: callable = self.__get_func()
            result = callfunc(self)
            resp.set_code(200).set_msg(str(result))
        except Exception as e:
            resp.set_code(201).set_error(str(e))
        finally:
            self.write(resp.as_str())

    def __get_func(self) -> callable:
        path = self.get_url()
        routers = self.routers()
        callfunc = routers.get(path, None)
        if callfunc is None:
            raise Exception("invalid uri:'{}'".format(path))
        return callfunc

    def send_tx(self) -> str:
        txstatus = TxStatus.PENDING
        info = self.get_argument("tx")
        info["status"] = txstatus
        tx = Transaction.from_json(info)
        assert self.bcstates.txpool.put_tx(tx)
        return tx.hash().hex()

    def query_tx(self) -> str:
        th: str = self.get_argument("txhash")
        txhash: bytes = bytes.fromhex(th)
        res = self.bcstates.txindexer.query(txhash)
        if res is None:
            raise Exception(f"cannot find txhash: {th}")
        return json.dumps(res.as_json())

    def call_ctr(self) -> str:
        toctr: str = self.get_argument("to")
        data: str = urllib.parse.unquote(self.get_argument("data"))
        res: str = self.bcstates.query_state(toctr, data)
        return res

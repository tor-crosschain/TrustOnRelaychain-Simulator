import pickle
import json
import hashlib
from enum import Enum
from chain_simulator.blockchain.context import Context
from chain_simulator.vm.icode import CodeMeta
from chain_simulator.vm.store import BaseStore
from chain_simulator.types.transaction import Transaction
from chain_simulator.types.block import Block


class ExecType(Enum):
    DEPLOY: int = 0
    EXEC: int = 1


class Response:
    def __init__(self, code: int = 1, out="") -> None:
        self.code = int(code)
        self.out = out if out is not None else ""

    def to_dict(self) -> dict:
        return {"code": self.code, "out": self.out}

    def to_str(self) -> str:
        return json.dumps(self.to_dict())
    
    @staticmethod
    def from_str(s: str) -> "Response":
        return Response(**json.loads(s))


class Executor(object):
    """
    Execute transactions
    """

    def __init__(self, _ctx: Context, _store: BaseStore) -> None:
        self._store = _store
        self._ctx = _ctx

    def execute_block(self, block: Block) -> None:
        txs = block.txs
        for idx, tx in enumerate(txs):
            self.execute_tx(block.height, idx, tx)

    async def execute_tx(self, height: int, idx: int, tx: Transaction) -> Response:
        to = tx.to
        data = tx.data
        if to == "" or to is None:
            resp = self.deploy(height, idx, data)
        else:
            resp = await self.execute(to, data)
        return resp

    def deploy(self, height: int, idx: int, _data: str, name=None) -> Response:
        """Execute transaction

        :param height: Block height where the transaction is located
        :type height: int
        :param idx: Transaction index in the block
        :type idx: int
        :param tx: Transaction content
        :type tx: Transaction
        """
        data = bytes.fromhex(_data)
        ctr: CodeMeta = pickle.loads(data)
        ctr.store = self._store
        ctr.ctx = self._ctx
        try:
            ctr.init()
        except Exception as e:
            code = 0
            out = str(e)
            return Response(code=code, out=out)
        if name is None:
            m = hashlib.sha256()
            m.update(height.to_bytes(8, "big"))
            m.update(idx.to_bytes(8, "big"))
            m.update(data)
            _hash = m.hexdigest()
        else:
            _hash = name
        self._store.set(_hash, pickle.dumps(ctr).hex())
        out = _hash
        return Response(code=1, out=out)

    async def execute(self, to: str, data: str) -> Response:
        """Execute specific contract function
        :param tx: _description_
        :type tx: Transaction
        """
        ctrbytes = bytes.fromhex(self._store.get(to))
        ctr: CodeMeta = pickle.loads(ctrbytes)
        ctr.store = self._store
        ctr.ctx = self._ctx
        try:
            out = await ctr.exec(data)
            code = 1
        except Exception as e:
            code = 0
            out = str(e)
        return Response(code=code, out=out)

    def query(self, to: str, data: str) -> Response:
        ctrbytes = bytes.fromhex(self._store.get(to))
        ctr: CodeMeta = pickle.loads(ctrbytes)
        ctr.store = self._store
        ctr.ctx = self._ctx
        try:
            out = ctr.query(data)
            out = str(out)
            code = 1
        except Exception as e:
            code = 0
            out = str(e)
        return Response(code=code, out=out)

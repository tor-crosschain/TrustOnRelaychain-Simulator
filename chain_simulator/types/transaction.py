from __future__ import annotations

import hashlib
import json
from functools import lru_cache
from enum import Enum
from typing import Dict


class TxStatus(Enum):
    INVALID: int = 0
    CREATED: int = 1
    PENDING: int = 2
    PROPOSING: int = 3
    SUCCESS: int = 4
    FAILED: int = 5

    def __repr__(self) -> int:
        return str(self.value)


class TranMemo:
    CTXSRC: str = "CTX-SRC"
    CTXDST: str = "CTX-DST"
    CTXINTER: str = "CTX-INTER"
    CTXHDR: str = "CTX-HEADER"
    CTXDSTL1: str = "CTX-DST-L1"  # ToR's L1 level verification, L2 level verification can directly use CTXDST identifier
    CTXINTERUV: str = "CTX-INTER-UV"

    MODENOR: str = "MODE-NOR"
    MODEAOR: str = "MODE-AOR"
    MODETOR: str = "MODE-TOR"

    @staticmethod
    def is_dst_xtx(_type: str) -> bool:
        # Whether it's a target chain cross-chain transaction (excluding block header sync transactions)
        return _type == TranMemo.CTXDST

    @staticmethod
    def is_inter_xtx(_type: str) -> bool:
        # Whether it's a relay chain cross-chain transaction (excluding block header sync transactions)
        return _type == TranMemo.CTXINTER

    @staticmethod
    def is_src_xtx(_type: str) -> bool:
        # Whether it's a source chain cross-chain transaction
        return _type == TranMemo.CTXSRC

    @staticmethod
    def is_header(_type: str) -> bool:
        # Whether it's a block header sync transaction
        return _type == TranMemo.CTXHDR

    @staticmethod
    def is_otx(_type: str) -> bool:
        # Whether it's a normal transaction
        return _type not in (
            TranMemo.CTXSRC,
            TranMemo.CTXDST,
            TranMemo.CTXHDR,
            TranMemo.CTXINTER,
        )

    @staticmethod
    def mode_unified(mode: str) -> str:
        if mode == TranMemo.MODEAOR:
            return TranMemo.MODEAOR
        if mode == TranMemo.MODENOR:
            return TranMemo.MODENOR
        if mode == TranMemo.MODETOR:
            return TranMemo.MODETOR
        if mode.lower() == "nor":
            return TranMemo.MODENOR
        if mode.lower() == "tor":
            return TranMemo.MODETOR
        if mode.lower() == "aor":
            return TranMemo.MODEAOR


class Transaction(object):
    def __init__(
        self,
        sender: str = "",
        to: str = "",
        data: str = "",
        memo: str = "{}",
        height: int = 0,
        status: TxStatus = TxStatus.INVALID,
        out: str = "",
    ) -> None:
        """Transaction data structure

        :param sender: Sender, defaults to ""
        :type sender: str, optional
        :param to: Receiver, used as contract identifier, defaults to ""
        :type to: str, optional
        :param data: Data body, hexadecimal string, defaults to ""
        :type data: str, hexadecimal string, optional
        :param memo: Memo information, defaults to ""
        :type memo: str, JSON string, optional
        :param height: Block height, defaults to 0
        :type height: int, optional
        :param status: Transaction status, defaults to TxStatus.INVALID
        :type status: TxStatus, optional
        """

        # basic property
        self.sender: str = sender
        self.to: str = to
        self.data: str = data
        self.memo: str = memo

        # dynamic property, changing with consensus
        assert isinstance(height, int)
        self.height: int = height
        self.status: TxStatus = status
        self.out: str = out

    @lru_cache(maxsize=1)
    def hash(self) -> bytes:
        m = hashlib.sha256()
        m.update(self.sender.encode())
        m.update(self.to.encode())
        m.update(self.data.encode())
        # m.update(self.memo.encode())
        # m.update(str(self.status.value).encode())
        return m.digest()

    @lru_cache(maxsize=1)
    def receipt_hash(self) -> bytes:
        """Calculate receipt hash after transaction execution completes and execution status and return content are obtained
        :return: receipt hash in bytes
        :rtype: bytes
        """
        _h = self.hash()
        m = hashlib.sha256()
        m.update(_h)
        m.update((self.height).to_bytes(8, "big"))
        m.update((int(self.status.value)).to_bytes(8, "big"))
        m.update(self.out.encode())
        return m.digest()

    @lru_cache(maxsize=1)
    def as_json(self) -> Dict:
        return {
            "sender": self.sender,
            "to": self.to,
            "data": self.data,
            "memo": self.memo,
            "height": self.height,
            "status": self.status.value,
            "out": self.out,
            "hash": self.hash().hex(),
            "receiptHash": self.receipt_hash().hex(),
        }

    @staticmethod
    def from_json(info: dict) -> Transaction:
        assert isinstance(info, dict), "arg must be json"
        sender = info["sender"]
        to = info["to"]
        data = info["data"]
        memo = info.get("memo", "{}")
        height = info.get("height", 0)
        status = info.get("status", TxStatus.INVALID)
        out = info.get("out", "")
        if isinstance(status, int):
            status = TxStatus(status)
        tx = Transaction(
            sender=sender,
            to=to,
            data=data,
            memo=memo,
            status=status,
            height=height,
            out=out,
        )
        return tx

    def _check_data_valid(self) -> bool:
        try:
            if not self.to:
                data = self.data
                return True
            else:
                data = json.loads(self.data)
            assert data.get("funcname", None) is not None, "funcname not exists"
            assert data.get("input", None) is not None, "input not exists"
        except Exception:
            return False
        return True

    def isvalid(self) -> bool:
        return self._check_data_valid()


class TransactionIndexer(object):
    def __init__(self) -> None:
        self.__map = {}

    def store(self, tx: Transaction):
        txhash = tx.hash()
        self.__map[txhash] = tx

    def query(self, txhash: bytes) -> Transaction | None:
        res = self.__map.get(txhash, None)
        return res


class TransactionReceipt(object):
    def __init__(self, tx: Transaction, out: str = "", code: int = 1) -> None:
        self.tx: Transaction = tx
        self.out: str = out
        self.code: int = code  # 0: false; 1: true
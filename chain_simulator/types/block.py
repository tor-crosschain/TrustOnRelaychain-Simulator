from __future__ import annotations

import hashlib
import json
from functools import lru_cache
from chain_simulator.types.transaction import Transaction
from typing import List, Dict, Optional


class Block(object):
    def __init__(self) -> None:
        self.height: int = 0
        self.tx_root: bytes = b""
        self.receipt_root: bytes = b""
        self.timestamp: float = 0.0
        self.txs: List[Transaction] = []

    @lru_cache(maxsize=1)
    def hash(self) -> bytes:
        message = self.to_bytes()
        h = hashlib.sha256(message)
        return h.digest()

    @lru_cache(maxsize=1)
    def header(self) -> Dict:
        """Returns the block header

        :return: Data in JSON format
        :rtype: Dict
        """
        return {
            "height": self.height,
            "hash": self.hash().hex(),
            "txroot": self.tx_root.hex(),
            "receiptroot": self.receipt_root.hex(),
            "timestamp": self.timestamp,
        }

    def to_msg(self) -> str:
        return ""

    @lru_cache(maxsize=1)
    def to_bytes(self) -> bytes:
        return json.dumps(self.__base_block()).encode()

    @lru_cache(maxsize=1)
    def __base_block(self) -> Dict:
        baseblock = {
            "height": self.height,
            "tx_root": self.tx_root.hex(),
            "receipt_root": self.receipt_root.hex(),
            "timestamp": self.timestamp,
            "txs": [tx.as_json() for tx in self.txs],
        }
        return baseblock

    @lru_cache(maxsize=1)
    def as_json(self) -> Dict:
        baseblock = self.__base_block()
        baseblock.update(
            {
                "hash": self.hash().hex(),
            }
        )
        return baseblock

    @staticmethod
    def from_json(data: dict) -> Block:
        self = Block()
        self.height = data["height"]
        self.tx_root = bytes.fromhex(data["tx_root"])
        self.receipt_root = bytes.fromhex(data["receipt_root"])
        self.timestamp = float(data["timestamp"])
        self.txs = [Transaction.from_json(tx) for tx in data["txs"]]
        return self

    @lru_cache(maxsize=1)
    def as_str(self) -> str:
        return json.dumps(self.as_json())

    @staticmethod
    def from_str(data: str) -> Block:
        return Block.from_json(json.loads(data))

    @staticmethod
    def from_json(bj: Dict) -> Block:
        block = Block()
        block.height = bj.get("height", 0)
        block.tx_root = bytes.fromhex(bj.get("tx_root", "00"))
        block.receipt_root = bytes.fromhex(bj.get("receipt_root", "00"))
        block.timestamp = bj.get("timestamp", 0.0)
        block.txs = [Transaction.from_json(tx) for tx in bj.get("txs", [])]
        return block


class BlockStorage(object):
    def __init__(self) -> None:
        self.blocks: List[Block] = []

    def block_num(self) -> int:
        return len(self.blocks) - 1

    def get_block_by_height(self, height: int) -> Optional[Block]:
        assert isinstance(height, int)
        if height > self.block_num():
            return None
        return self.blocks[height]

    def append(self, _block_data: str) -> None:
        assert isinstance(_block_data, str)
        new_block = Block.from_str(_block_data)
        assert new_block.height == self.block_num() + 1
        self.blocks.append(new_block)

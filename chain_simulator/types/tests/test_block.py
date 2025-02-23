from chain_simulator.types.block import Block


def test_from_json():
    bjs = [
        {
            "height": 10,
            "tx_root": "00",
            "receipt_root": "00",
            "timestamp": 1.0,
            "txs": [],
        },
        {
            "height": 0,
            "receipt_root": "00",
            "txs": [
                {
                    "sender": "alice",
                    "to": "bob",
                    "data": "sss",
                    "memo": "as",
                    "height": 10,
                    "status": 0,
                }
            ],
        },
    ]
    for bj in bjs:
        Block.from_json(bj)


def test_header():
    block = Block()
    assert isinstance(block.header(), dict)


def test_to_bytes():
    block = Block()
    assert isinstance(block.to_bytes(), bytes)


def test_as_json():
    block = Block()
    assert isinstance(block.as_json(), dict)


def test_hash():
    block = Block()
    assert isinstance(block.hash(), bytes)

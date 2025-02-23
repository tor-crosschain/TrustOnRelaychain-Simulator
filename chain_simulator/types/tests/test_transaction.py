from chain_simulator.types.transaction import Transaction, TxStatus


def test_hash():
    datas = [
        {
            "sender": "send0" + str(x),
            "to": "to0" + str(x),
            "data": "data0" + str(x),
            "memo": "memo0" + str(x),
        }
        for x in range(10)
    ]
    for data in datas:
        tx = Transaction.from_json(data)
        assert len(tx.hash()) == 32
        assert tx.hash() != 0x00

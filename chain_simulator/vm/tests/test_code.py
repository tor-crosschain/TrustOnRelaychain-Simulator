import json
import pickle
import pytest
from chain_simulator.blockchain.context import Context
from chain_simulator.types.block import Block
from chain_simulator.types.transaction import Transaction
from chain_simulator.vm.store import BaseStore
from chain_simulator.vm.executor import Executor
from chain_simulator.vm.tests.codes.code_add import CodeAdd
from chain_simulator.vm.base.CtrLightClient import CtrLightClient


async def test_add():
    store = BaseStore()
    ctx = Context()
    ctx.set(Block())
    exec = Executor(ctx, store)
    # deploy
    ctr = CodeAdd()
    param_deploy = {
        "to": "",
        "data": pickle.dumps(ctr).hex(),
    }
    tx = Transaction(to=param_deploy["to"], data=param_deploy["data"])
    resp = await exec.execute_tx(1, 1, tx)
    assert resp.code == 1, f"code is {resp.code}, out is {resp.out}"
    assert len(bytes.fromhex(resp.out)) == 32, f"out is {resp.out}"
    # execute
    param_exec = {
        "to": resp.out,
        "data": json.dumps({"func": "add", "arguments": ["a", 10]}),
    }
    tx2 = Transaction(to=param_exec["to"], data=param_exec["data"])
    resp2 = await exec.execute_tx(1, 2, tx2)
    assert resp2.code == 1, f"code is {resp2.code}, out is {resp2.out}"
    assert resp2.out == "20", f"out is {resp2.out}"
    # query
    param_qeury = json.dumps({"func": "", "arguments": ["a"]})
    resp3 = exec.query(to=resp.out, data=param_qeury)
    assert resp3.code == 1, f"code is {resp3.code}, out is {resp3.out}"
    assert resp3.out == "['20']", f"out is {resp3.out}"
    v3 = store.get("a")
    assert v3 == "20", f"a in store is {resp3.out}"


async def test_lightclient():
    store = BaseStore()
    ctx = Context()
    ctx.set(Block())
    exec = Executor(ctx, store)
    # deploy
    ctr = CtrLightClient()
    param_deploy = {
        "to": "",
        "data": pickle.dumps(ctr).hex(),
    }
    tx = Transaction(to=param_deploy["to"], data=param_deploy["data"])
    resp = await exec.execute_tx(1, 1, tx)
    assert resp.code == 1, f"code is {resp.code}, out is {resp.out}"
    assert len(bytes.fromhex(resp.out)) == 32, f"out is {resp.out}"

    contract_name = resp.out
    # set chainid
    param_chainid = {
        "to": contract_name,
        "data": json.dumps({"func": "set_paraid", "arguments": ["para01"]}),
    }
    tx = Transaction(to=param_chainid["to"], data=param_chainid["data"])
    resp = await exec.execute_tx(1, 1, tx)
    assert resp.code == 1, f"code is {resp.code}, out is {resp.out}"
    assert len(bytes.fromhex(resp.out)) == 0, f"out is {resp.out}"

    # set chaintype
    param_chaintype = {
        "to": contract_name,
        "data": json.dumps({"func": "set_paratype", "arguments": ["Ethereum"]}),
    }
    tx = Transaction(to=param_chaintype["to"], data=param_chaintype["data"])
    resp = await exec.execute_tx(1, 1, tx)
    assert resp.code == 1, f"code is {resp.code}, out is {resp.out}"
    assert len(bytes.fromhex(resp.out)) == 0, f"out is {resp.out}"

    # sync header success
    header_height = 10
    param_exec = {
        "to": contract_name,
        "data": json.dumps(
            {
                "func": "header_sync",
                "arguments": ["para01", "Tendermint", header_height, "header10"],
            }
        ),
    }
    tx2 = Transaction(to=param_exec["to"], data=param_exec["data"])
    resp2 = await exec.execute_tx(1, 2, tx2)
    assert resp2.code == 1, f"code is {resp2.code}, out is {resp2.out}"
    assert resp2.out == "header-para01-10", f"out is {resp2.out}"

    # sync header fail, error func name
    param_exec = {
        "to": contract_name,
        "data": json.dumps(
            {
                "func": "header_sync_xxx",
                "arguments": ["para01", "Tendermint", 10, "header10"],
            }
        ),
    }
    tx3 = Transaction(to=param_exec["to"], data=param_exec["data"])
    resp3 = await exec.execute_tx(1, 3, tx3)
    assert resp3.code == 0, f"code is {resp3.code}, out is {resp3.out}"
    assert resp3.out == "func(_header_sync_xxx) is illegal", f"out is {resp3.out}"

    # validate state success
    param_exec = {
        "to": contract_name,
        "data": json.dumps(
            {
                "func": "validate_state",
                "arguments": ["para01", "Tendermint", 10, "statebabala"],
            }
        ),
    }
    tx4 = Transaction(to=param_exec["to"], data=param_exec["data"])
    resp4 = await exec.execute_tx(1, 2, tx4)
    assert resp4.code == 1, f"code is {resp4.code}, out is {resp4.out}"
    assert resp4.out == "state-para01-10-1", f"out is {resp4.out}"

    # validate state fail, error unsynced header
    param_exec = {
        "to": contract_name,
        "data": json.dumps(
            {
                "func": "validate_state",
                "arguments": ["para01", "Tendermint", 11, "statebabala"],
            }
        ),
    }
    tx5 = Transaction(to=param_exec["to"], data=param_exec["data"])
    resp5 = await exec.execute_tx(1, 2, tx5)
    assert resp5.code == 0, f"code is {resp5.code}, out is {resp5.out}"
    assert resp5.out == "cannot find header: header-para01-11", f"out is {resp5.out}"

    # query header success
    param_qeury = json.dumps({"func": "query_header", "arguments": ["para01", 10]})
    resp3 = exec.query(to=contract_name, data=param_qeury)
    assert resp3.code == 1, f"code is {resp3.code}, out is {resp3.out}"
    assert resp3.out == json.dumps(
        {"header": "header10", "cs_height": 0}
    ), f"out is {resp3.out}"

    # query header fail, error height
    param_qeury = json.dumps({"func": "query_header", "arguments": ["para01", 11]})
    resp3 = exec.query(to=contract_name, data=param_qeury)
    assert resp3.code == 0, f"code is {resp3.code}, out is {resp3.out}"
    assert resp3.out == "cannot find header: header-para01-11", f"out is {resp3.out}"

    # query header cnt
    param_qeury = json.dumps({"func": "query_header_maxn", "arguments": ["para01"]})
    resp3 = exec.query(to=contract_name, data=param_qeury)
    assert resp3.code == 1, f"code is {resp3.code}, out is {resp3.out}"
    assert resp3.out == f"{header_height}", f"out is {resp3.out}"
    # header sync again for querying header cnt
    header_height_11 = 11
    param_exec = {
        "to": contract_name,
        "data": json.dumps(
            {
                "func": "header_sync",
                "arguments": ["para01", "Tendermint", header_height_11, "header10"],
            }
        ),
    }
    tx2 = Transaction(to=param_exec["to"], data=param_exec["data"])
    resp2 = await exec.execute_tx(1, 2, tx2)
    assert resp2.code == 1, f"code is {resp2.code}, out is {resp2.out}"
    assert resp2.out == "header-para01-11", f"out is {resp2.out}"
    # query header cnt again
    param_qeury = json.dumps({"func": "query_header_maxn", "arguments": ["para01"]})
    resp3 = exec.query(to=contract_name, data=param_qeury)
    assert resp3.code == 1, f"code is {resp3.code}, out is {resp3.out}"
    assert resp3.out == f"{header_height_11}", f"out is {resp3.out}"

    # query state success
    param_qeury = json.dumps({"func": "query_state", "arguments": ["para01", 10, 1]})
    resp3 = exec.query(to=contract_name, data=param_qeury)
    assert resp3.code == 1, f"code is {resp3.code}, out is {resp3.out}"
    assert resp3.out == "statebabala", f"out is {resp3.out}"

    # query state fail, error idx
    param_qeury = json.dumps({"func": "query_state", "arguments": ["para01", 10, 2]})
    resp3 = exec.query(to=contract_name, data=param_qeury)
    assert resp3.code == 0, f"code is {resp3.code}, out is {resp3.out}"
    assert resp3.out == "cannot find state: state-para01-10-2", f"out is {resp3.out}"

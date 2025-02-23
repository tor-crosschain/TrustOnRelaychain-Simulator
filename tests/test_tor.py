import math
import time
import requests
import asyncio
import json
import threading
import random
import multiprocessing
from multiprocessing import synchronize
from typing import Tuple, List
from chain_simulator.types.transaction import TranMemo
from chain_simulator.types.block import Block
from chain_simulator.service.api_service import ApiService
from chain_simulator.blockchain.blockchain import Blockchain
from chain_simulator.mempool.mempool import AsyncMemPool
from chain_simulator.config.config import Config
from relayer.connector.connector import Connector
from relayer.relayer.relayer import Relayer, Mode, ToRRelayerType


TXNUM = 10  # Total number of transactions
XTXNUM = int(TXNUM * 1.0)  # Cross-chain transaction ratio
CHAINNUM = 3  # Number of parallel chains

configs = [Config(block_size=100, block_interval=1, mempool_size=1000000)] * CHAINNUM
inter_config = Config(block_size=500, block_interval=1, mempool_size=1000000)
configs = [inter_config] + configs  


def pre_test(
    chain_num: int,
    classes: List[int], 
) -> Tuple[
    List[multiprocessing.Process],
    List[str],
    List[Tuple[synchronize.Event, synchronize.Event]],
    List[str],
]:
    def thread_proxy(
        args: dict,
        stop_api_event: multiprocessing.Event,
        stop_bc_event: multiprocessing.Event,
        config: Config,
    ):
        """run tornado service in a seperate thread

        :param serv: tornado api service
        :type serv: ApiService
        """

        mpool = AsyncMemPool(maxsize=config.mempool_size)
        bc = Blockchain(pool=mpool, config=config)
        api_serv = ApiService(mpool=mpool, bc=bc)
        cors = [api_serv.run_app(args), bc.start()]

        async def stopapiserv():
            while True:
                if stop_api_event.is_set():
                    break
                await asyncio.sleep(1)
            api_serv.stop_event.set()
            await asyncio.sleep(0.5)

        async def stopbc():
            while True:
                if stop_bc_event.is_set():
                    break
                await asyncio.sleep(1)
            
            bc.stop()
            await asyncio.sleep(config.block_interval)  # 等一个共识周期

        cors += [stopapiserv(), stopbc()]
       
        asyncio.run(
            asyncio.wait(
                cors,
            )
        )
        print(f"process-{multiprocessing.current_process().name} stopped!")

    procs: List[multiprocessing.Process] = []
    hosts: List[str] = []
    events: List[Tuple[multiprocessing.Event, multiprocessing.Event]] = []
    assert len(classes) == 2, "chain class num must be 2"
    classes: List[str] = (
        ["Tendermint"] + ["Ethereum"] * classes[0] + ["Tendermint"] * classes[1]
    )  
    for i in range(chain_num):
        args = {"port": 9000 + i}
        hosts.append(f"127.0.0.1:{args['port']}")
        stop_api_event = multiprocessing.Event()
        stop_bc_event = multiprocessing.Event()
        events.append((stop_api_event, stop_bc_event))
        proc = multiprocessing.Process(
            target=thread_proxy,
            args=(args, stop_api_event, stop_bc_event, configs[i]),
        )
        procs.append(proc)

    for proc in procs:
        proc.start()

    time.sleep(1)  

    return procs, hosts, events, classes


def send_tx(
    chainnum: int, classes: List[str], paraid: int, host: str, txnum: int
) -> None:
    # The destination chain identifier for all transactions, if the identifier is -1, it is a normal transaction, if the identifier is not 0, it is a cross-chain transaction, and the identifier is the destination chain identifier
    dsts = [-1] * (TXNUM - XTXNUM) + [1] * XTXNUM
    dsts = random.sample(dsts, len(dsts))
    for i in range(len(dsts)):
        if dsts[i] == 1:
            x = None
            while True:
                x = random.randint(0, chainnum - 1)  # Randomly select the destination chain identifier
                if x != paraid:  # Select 1 identifier that is not the current chain
                    break
            assert x is not None
            dsts[i] = x
    url_send_tx = f"http://{host}/send_tx"
    for idx in range(TXNUM):
        if dsts[idx] >= 0:  # Determine if it is a cross-chain transaction
            # Send a transaction to the app_init function of the lightclient contract
            dstid = int(dsts[idx])
            memo = {"type": TranMemo.CTXSRC, "dst": dsts[idx]}
            # Source chain timestamp
            memo["ts"] = {"init": time.time()}
            data = {
                "tx": {
                    "sender": f"send/{paraid}/{idx}",
                    "to": "lightclient",
                    "data": json.dumps(
                        {
                            "func": "app_init",
                            "arguments": [dstid, classes[dstid], "crosschain-data"],
                        }
                    ),
                    "memo": json.dumps(memo),
                }
            }
        else:
            memo = {"type": "TX"}
            # Source chain timestamp
            memo["ts"] = {"init": time.time()}
            data = {
                "tx": {
                    "sender": f"send/{paraid}/{idx}",
                    "to": "base",
                    "data": json.dumps({"arguments": [f"a{idx}", idx]}),
                    "memo": json.dumps(memo),
                }
            }

        resp_send_tx = requests.post(url=url_send_tx, data=json.dumps(data), timeout=10)
        assert resp_send_tx.status_code == 200
        resp = json.loads(resp_send_tx.text)
        assert resp["error"] == "", f"response error: {resp['error']}"
        assert resp["code"] == 200, f"response code: {resp['code']}"
        # time.sleep(0.01)


def send_tx_parallelism(
    hosts: List[str], classes: List[str]
) -> List[multiprocessing.Process]:
    procs: List[multiprocessing.Process] = []
    txnum = 20
    for paraid, host in enumerate(hosts):
        proc = multiprocessing.Process(
            target=send_tx, args=(len(hosts), classes, paraid, host, txnum)
        )
        procs.append(proc)

    for proc in procs:
        proc.start()

    return procs


def build_relayers(
    interhost: str, hosts: List[str]
) -> Tuple[List[Tuple[Relayer, Relayer]], List[Tuple[Relayer, Relayer]]]:
    inter_pid = 30000
    # 1. Build PAP type gateway
    relayer_pairs_pap = []
    lh = len(hosts)

    def create_relayers(i: int):
        for j in range(i + 1, lh):
            print(f"build <{i}, {j}>")
            src_connector = Connector(host=hosts[i], sender=f"proc/{i}/{j}/src")
            tgt_connector = Connector(host=hosts[j], sender=f"proc/{i}/{j}/dst")
            inter_connector = Connector(
                host=interhost, sender=f"proc/{i}/{j}/inter/pap"
            )
            relayer0 = Relayer(
                src_connector,
                tgt_connector,
                mode=Mode.MODETOR,
                inter=inter_connector,
                rlytp=ToRRelayerType.PAP,
            )  # ToR
            relayer1 = Relayer(
                tgt_connector,
                src_connector,
                mode=Mode.MODETOR,
                inter=inter_connector,
                rlytp=ToRRelayerType.PAP,
            )  # ToR
            assert relayer0.src.pid == i, f"src pid is { relayer0.src.pid }"
            assert relayer0.dst.pid == j, f"dsr pid is { relayer0.dst.pid }"
            relayer_pairs_pap.append((relayer0, relayer1))

    procs = []
    for i in range(lh):
        proc = threading.Thread(target=create_relayers, args=(i,))
        # proc = multiprocessing.Process(target=create_relayers, args=(i, ))
        procs.append(proc)

    for proc in procs:
        proc.start()
    for proc in procs:
        proc.join()

    # 2. Build PAR type gateway
    relayer_pairs_par = []
    for i in range(lh):
        src_connector = Connector(host=hosts[i], sender=f"proc/{i}/{inter_pid}/para")
        tgt_connector = Connector(
            host=interhost,
            sender=f"proc/{i}/{inter_pid}/inter",
            isinter=True,  # Mark that the connector points to the relay chain
        )
        relayer0 = Relayer(
            src_connector,
            tgt_connector,
            mode=Mode.MODETOR,
            rlytp=ToRRelayerType.PAR,
        )  # ToR
        relayer1 = Relayer(
            tgt_connector,
            src_connector,
            mode=Mode.MODETOR,
            rlytp=ToRRelayerType.PAR,
        )  # ToR
        relayer_pairs_par.append((relayer0, relayer1))

    return relayer_pairs_pap, relayer_pairs_par


def check(
    host: str,
    val,
    target: int,
    min_init,
    max_last_commit,
    latency_sum,
    ctxs: multiprocessing.Queue,
):
    tempctxs = []
    assert isinstance(host, str)
    assert isinstance(target, int)
    url = f"http://{host}/query_block_number"
    r = requests.get(url)
    resp = json.loads(r.text)
    bn = int(resp["msg"])
    i = 1
    while True:
        if i > bn:
            while True:
                url = f"http://{host}/query_block_number"
                r = requests.get(url)
                resp = json.loads(r.text)
                bn = int(resp["msg"])
                if i <= bn:
                    break
                time.sleep(configs[1].block_interval)
        url_block = f"http://{host}/query_block?bn={i}"
        r = requests.get(url_block)
        resp = json.loads(r.text)
        blk: dict = json.loads(resp["msg"])
        assert blk["height"] == i
        block = Block.from_json(blk)
        txs = block.txs
        for tx in txs:
            memo = json.loads(tx.memo)
            if memo["type"] == TranMemo.CTXDST:
                tempctxs.append(memo)
                with val.get_lock():
                    val.value += 1
                last_commit = memo["ts"]["commit"][-1]
                init = memo["ts"]["init"]
                with latency_sum.get_lock():
                    latency_sum.value += last_commit - init
                with min_init.get_lock():
                    if min_init.value > init:
                        min_init.value = init
                with max_last_commit.get_lock():
                    if max_last_commit.value < last_commit:
                        max_last_commit.value = last_commit
        with val.get_lock():
            if val.value >= target:
                print(f"val.value: {val.value}")
                break
        i += 1
    # json.dump(ctxs, open("ctxmemos.json", 'w'))
    for item in tempctxs:
        ctxs.put(item)


def get_last_xtx_block(idx: int, host: str) -> int:
    """Query the number of the last block with cross-chain transactions"""
    assert isinstance(idx, int)
    assert isinstance(host, str)
    cnct = Connector(host=host)
    maxbn = cnct.query_block_number()
    for bn in range(maxbn, 0, -1):
        block = cnct.query_block(bn)
        txs = block.txs
        for tx in txs:
            memo = json.loads(tx.memo)
            if memo["type"] == TranMemo.CTXSRC:
                return bn
    raise Exception("not find valid xtx block!")


def check_inter_header_number(interhost: str, hosts: str):
    """Check if the number of blocks in the relay chain contract is greater than the number of blocks in the parallel chain"""
    cnct = Connector(host=interhost)
    for idx, host in enumerate(hosts):
        max_xtx_bn = get_last_xtx_block(idx, host)
        max_para_xbn = cnct.query_max_xbn(idx)
        assert max_para_xbn >= max_xtx_bn
        for i in range(1, max_xtx_bn):
            header_data = cnct.query_synced_header(pid=idx, height=i)
            header = header_data.get("header", None)
            assert header
            assert header["height"] == i


def query_inter_workload(interhost: str) -> int:
    cnct = Connector(host=interhost)
    maxbn = cnct.query_block_number()
    txnums = 0
    for i in range(1, maxbn + 1):
        block: Block = cnct.query_block(i)
        txnums += len(block.txs)
    return txnums


def set_paraid(host: str, paraid: int):
    url_set_id = f"http://{host}/send_tx"
    memo = {"type": "TX"}
    data = {
        "tx": {
            "sender": f"send/{paraid}/{set}",
            "to": "lightclient",
            "data": json.dumps({"func": "set_paraid", "arguments": [paraid]}),
            "memo": json.dumps(memo),
        }
    }
    resp_send_tx = requests.post(url_set_id, data=json.dumps(data), timeout=10)
    assert resp_send_tx.status_code == 200
    resp = json.loads(resp_send_tx.text)
    assert resp["error"] == "", f"response error: {resp['error']}"
    assert resp["code"] == 200, f"response code: {resp['code']}"


def set_paratype(host: str, paratype: str):
    url_set_type = f"http://{host}/send_tx"
    memo = {"type": "TX"}
    data = {
        "tx": {
            "sender": f"send/{paratype}/{set}",
            "to": "lightclient",
            "data": json.dumps({"func": "set_paratype", "arguments": [paratype]}),
            "memo": json.dumps(memo),
        }
    }
    resp_send_tx = requests.post(url_set_type, data=json.dumps(data), timeout=10)
    assert resp_send_tx.status_code == 200
    resp = json.loads(resp_send_tx.text)
    assert resp["error"] == "", f"response error: {resp['error']}"
    assert resp["code"] == 200, f"response code: {resp['code']}"


def set_crossinfo(hosts: List[str], pids: List[int], classes: List[str]):
    for idx, host in enumerate(hosts):
        set_paraid(host, pids[idx])
        set_paratype(host, classes[idx])


def stop_mining(host: str):
    print(f"stop mining: {host}")
    url = f"http://{host}/stop_mining"
    r = requests.post(url)
    assert r.status_code == 200


def start_mining(host: str):
    print(f"start mining: {host}")
    url = f"http://{host}/start_mining"
    r = requests.post(url)
    assert r.status_code == 200


def test_tor():
    """Test cross-chain interaction between chain_num chains, using ToR cross-chain mode
    There is 1 relay chain in the system;
    There are n parallel chains in the system;
    Parallel chains use PAP type gateways (only responsible for synchronizing cross-chain transactions), and parallel chains and relay chains use PAR type gateways (only responsible for synchronizing block headers);
    The number of transactions sent to each chain is fixed, the cross-chain transaction ratio is fixed, the destination chain identifier of the cross-chain transaction is random;
    """
    assert CHAINNUM >= 2
    classone = CHAINNUM // 2
    classtwo = CHAINNUM - classone
    procs_serv, hosts, events, classes = pre_test(
        chain_num=CHAINNUM + 1, classes=[classone, classtwo]
    )  

    interhost = hosts[0]
    interpid = 30000
    # Set the relay chain id, chain type
    set_crossinfo(hosts=hosts[0:1], pids=[interpid], classes=classes[0:1])

    hosts = hosts[1:]
    classes = classes[1:]
    # Set the parallel chain id, chain type
    set_crossinfo(hosts=hosts, pids=list(range(len(hosts))), classes=classes)

    # Wait for each chain to include the set paraid/paratype transaction
    time.sleep(configs[1].block_interval * 2)

    # Stop blockchain block production
    for host in hosts:
        stop_mining(host)
    stop_mining(interhost)

    # Build relayer
    relayer_pairs_pap, relayer_pairs_par = build_relayers(interhost, hosts)
    relayers_all = relayer_pairs_pap + relayer_pairs_par

    # Start relay process
    procs_rly: List[Tuple[multiprocessing.Process, multiprocessing.Process]] = []
    for rly0, rly1 in relayers_all:
        proc1 = multiprocessing.Process(target=rly0.start_one_way)
        proc2 = multiprocessing.Process(target=rly1.start_one_way)
        procs_rly.append((proc1, proc2))
    for proc0, proc1 in procs_rly:
        proc0.start()
        proc1.start()

    # Start blockchain block production
    for host in hosts:
        start_mining(host)
    start_mining(interhost)

    # Send transactions to all parallel chains in parallel
    procs_sendtx = send_tx_parallelism(hosts, classes)

    # Wait for the transaction sending process to end
    for proc in procs_sendtx:
        proc.join()
    print("============process sendtx finished!")

    # Check if the number of transactions with memo.type == CTX-DST on all chains is the same as the number of cross-chain transactions
    target = XTXNUM * CHAINNUM
    check_procs = []
    val = multiprocessing.Value("i", 0)
    min_init = multiprocessing.Value("d", time.time() * 2)
    max_last_commit = multiprocessing.Value("d", 0)
    latency_sum = multiprocessing.Value("d", 0)
    ctxs = multiprocessing.Manager().Queue()
    for host in hosts:
        proc = multiprocessing.Process(
            target=check,
            args=(host, val, target, min_init, max_last_commit, latency_sum, ctxs),
        )
        check_procs.append(proc)
    for proc in check_procs:
        proc.start()
    for proc in check_procs:
        proc.join()

    # Each chain sent XTXNUM transactions, so a total of XTXNUM * CHAINNUM transactions were sent
    assert val.value == target

    # Close relayer
    for rly0, rly1 in relayers_all:
        rly0.stop()
        rly1.stop()
    for proc0, proc1 in procs_rly:
        proc0.join()
        proc1.join()
    print("============close relayer!")

    # Check the total number of relay chain block headers
    # check_inter_header_number(interhost, hosts)

    # Get the total number of relay chain transactions
    interalltx = query_inter_workload(interhost)

    # Close blockchain and service
    for stop_api_event, stop_bc_event in events:
        stop_bc_event.set()
        stop_api_event.set()
    for proc in procs_serv:
        proc.join()
    print("============close service!")

    ts_src = []
    ts_rly = []
    ts_dst = []
    while not ctxs.empty():
        memo = ctxs.get()
        # memostr = ctxs.get()
        # memo = json.loads(memostr)
        ts = memo["ts"]
        ts_src.append(ts["commit"][0] - ts["init"])
        rly = ts["relayer"]
        assert rly[2][0] == "send", f"relayer ts tag({rly[2][0]}) is invalid"
        assert rly[0][0] == "listened", f"relayer ts tag({rly[0][0]}) is invalid"
        ts_rly.append(ts["relayer"][2][1] - ts["relayer"][0][1])
        ts_dst.append(ts["commit"][1] - ts["relayer"][2][1])
    ts_src_avg = sum(ts_src) / len(ts_src)
    ts_rly_avg = sum(ts_rly) / len(ts_rly)
    ts_dst_avg = sum(ts_dst) / len(ts_dst)

    tps = target / (max_last_commit.value - min_init.value)
    print(f"tps: {tps}")
    latency_avg = latency_sum.value / target
    print(f"latency avg: {latency_avg}")
    print(f"interchain tx all num: {interalltx}")
    print(f"ts_src_avg: {ts_src_avg}")
    print(f"ts_rly_avg: {ts_rly_avg}")
    print(f"ts_dst_avg: {ts_dst_avg}")

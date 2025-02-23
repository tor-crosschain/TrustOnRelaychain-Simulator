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

TXNUM = 1  # Total number of transactions
XTXNUM = int(TXNUM * 1.0)  # Cross-chain transaction ratio
CHAINNUM = 3  # Number of parallel chains
configs = [Config(block_size=100, block_interval=1, mempool_size=1000000)] * CHAINNUM
inter_config = Config(block_size=500, block_interval=1, mempool_size=1000000)
configs = [inter_config] + configs  # Add relay chain configuration, and it must be placed in the first position

TPS_inter = inter_config.block_size // inter_config.block_interval
TPS_para = min(*([x.block_size // x.block_interval for x in configs]))
if TPS_inter < TPS_para * CHAINNUM:
    TPS_0 = TPS_inter
else:
    TPS_0 = CHAINNUM * TPS_para // 2


def pre_test(
    chain_num: int,
    class_num: List[int], 
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
            await asyncio.sleep(config.block_interval)  

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
    assert len(class_num) == 2, "chain class num must be 2"
    classes: List[str] = (
        ["Tendermint"] + ["Ethereum"] * class_num[0] + ["Tendermint"] * class_num[1]
    )  
    for i in range(chain_num):
        args = {"port": 9100 + i}
        hosts.append(f"localhost:{args['port']}")

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
    # All transaction destination chain identifiers, if the identifier is -1, it is a normal transaction, if the identifier is not 0, it is a cross-chain transaction, and the identifier is the destination chain identifier
    dsts = [-1] * (TXNUM - XTXNUM) + [1] * XTXNUM
    dsts = random.sample(dsts, len(dsts))
    for i in range(len(dsts)):
        if dsts[i] == 1:
            x = None
            while True:
                x = random.randint(0, chainnum - 1) 
                if x != paraid: 
                    break
            assert x is not None
            dsts[i] = x
    url_send_tx = f"http://{host}/send_tx"
    for idx in range(TXNUM):
        if dsts[idx] >= 0:  
            memo = {"type": TranMemo.CTXSRC, "dst": dsts[idx]}
        else:
            memo = {"type": "TX"}
        # Source chain timestamp
        memo["ts"] = {"init": time.time()}
        memo["mode"] = TranMemo.MODEAOR
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


def build_relayers(
    interhost: str, interpid: int, hosts: List[str]
) -> List[Tuple[Relayer, Relayer]]:
    lh = len(hosts)
    # Build the gateway between the relay chain and the parallel chain in the AoR mode
    relayer_pairs = []
    for i in range(lh):
        src_connector = Connector(host=hosts[i], sender=f"proc/{i}/{interpid}/para")
        tgt_connector = Connector(
            host=interhost,
            sender=f"proc/{i}/{interpid}/inter",
            isinter=True,  
        )
        relayer0 = Relayer(
            src_connector,
            tgt_connector,
            mode=Mode.MODEAOR,
        )  # AoR
        relayer1 = Relayer(
            tgt_connector,
            src_connector,
            mode=Mode.MODEAOR,
        )  # AoR
        relayer_pairs.append((relayer0, relayer1))
        print(f"relay between ({relayer0.src.pid}, {relayer0.dst.pid})")
        assert relayer0.src.pid == i, f"src pid is { relayer0.src.pid }"
        assert relayer0.dst.pid == interpid, f"dsr pid is { relayer0.dst.pid }"

    return relayer_pairs


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
        # print(f"val.value: {val.value}, target: {target}")
    # json.dump(ctxs, open("ctxmemos.json", 'w'))
    for item in tempctxs:
        ctxs.put(item)


def check_inter_ctx_number(interhost: str, target: int):
    """检查中继链上的跨链交易数量是否等于 target"""
    cnct = Connector(host=interhost)
    maxbn = cnct.query_block_number()
    count = 0
    for bn in range(1, maxbn + 1):
        block = cnct.query_block(bn)
        txs = block.txs
        for tx in txs:
            memo = json.loads(tx.memo)
            if memo["type"] == TranMemo.CTXINTER:
                count += 1
    assert target == count


def query_inter_workload(interhost: str) -> int:
    cnct = Connector(host=interhost)
    maxbn = cnct.query_block_number()
    txnums = 0
    for i in range(1, maxbn + 1):
        block: Block = cnct.query_block(i)
        txnums += len(block.txs)
    return txnums


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
    """!ABANDON! Because relayer transmit header from latest block of parachain but not first block, so 'assert header' will be wrong"""
    """Check the number of blocks in the relay chain contract is greater than the number of blocks in the parallel chain"""
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


def test_aor():
    """Test cross-chain interaction between chain_num chains, using the AoR cross-chain mode
    There is 1 relay chain in the system;
    There are n parallel chains in the system;
    The parallel chain and the relay chain interact (need to synchronize the block header and cross-chain transactions);
    The number of transactions sent to each chain is fixed, the cross-chain transaction ratio is fixed, and the destination chain identifier of the cross-chain transaction is random;
    """
    assert CHAINNUM >= 2
    procs_serv, hosts, events, classes = pre_test(
        chain_num=CHAINNUM + 1, class_num=[CHAINNUM, 0]
    )  # Add 1 relay chain

    interhost = hosts[0]
    interpid = 30000
    # Set the relay chain id, chain type
    set_crossinfo(hosts=hosts[0:1], pids=[interpid], classes=classes[0:1])
    hosts = hosts[1:]
    classes = classes[1:]
    # Set the parallel chain id, chain type
    set_crossinfo(hosts=hosts, pids=list(range(len(hosts))), classes=classes)

    # Send transactions to all parallel chains in parallel
    procs_sendtx = send_tx_parallelism(hosts, classes)

    # Wait for each chain to include the set paraid/paratype transaction
    # Note that the first config is the relay chain configuration
    time.sleep(configs[1].block_interval * 2)

    # Build relayer
    relayer_pairs = build_relayers(interhost, interpid, hosts)

    # Start relay process
    procs_rly: List[Tuple[multiprocessing.Process, multiprocessing.Process]] = []
    for rly0, rly1 in relayer_pairs:
        proc1 = multiprocessing.Process(target=rly0.start_one_way)
        proc2 = multiprocessing.Process(target=rly1.start_one_way)
        procs_rly.append((proc1, proc2))
    for proc0, proc1 in procs_rly:
        proc0.start()
        proc1.start()

    # Wait for the transaction sending process to end
    for proc in procs_sendtx:
        proc.join()
    print("============process sendtx finished!")

    # Check if the number of transactions with memo.type == CTX-DST on all chains is the same as the number of cross-chain transactions
    # When the number is the same, stop the blockchain program
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
    for rly0, rly1 in relayer_pairs:
        rly0.stop()
        rly1.stop()
    for proc0, proc1 in procs_rly:
        proc0.join()
        proc1.join()
    print("============close relayer!")

    # Check the total number of cross-chain transactions on the relay chain
    check_inter_ctx_number(interhost, target)

    # Check the total number of block headers on the relay chain
    # check_inter_header_number(interhost, hosts)

    # Get the total number of transactions on the relay chain
    interalltx = query_inter_workload(interhost)

    # Close the blockchain and service
    for stop_api_event, stop_bc_event in events:
        stop_bc_event.set()
        stop_api_event.set()
    for proc in procs_serv:
        proc.join()
    print("============close service!")

    ts_src = []
    ts_rly01 = []
    ts_inter = []
    ts_rly02 = []
    ts_dst = []
    while not ctxs.empty():
        memo = ctxs.get()
        # memostr = ctxs.get()
        # memo = json.loads(memostr)
        ts = memo["ts"]
        ts_src.append(ts["commit"][0] - ts["init"])
        rly = ts["relayer"]
        print(rly)
        ts_rly01.append(rly[2][1] - rly[0][1])
        ts_inter.append(ts["commit"][1] - rly[2][1])
        ts_rly02.append(rly[5][1] - rly[3][1])
        ts_dst.append(ts["commit"][2] - rly[5][1])
    ts_src_avg = sum(ts_src) / len(ts_src)
    ts_rly01_avg = sum(ts_rly01) / len(ts_rly01)
    ts_inter_avg = sum(ts_inter) / len(ts_inter)
    ts_rly02_avg = sum(ts_rly02) / len(ts_rly02)
    ts_dst_avg = sum(ts_dst) / len(ts_dst)

    tps = target / (max_last_commit.value - min_init.value)
    print(f"tps: {tps}")
    print("tps ratio: {:.2f}%".format((tps / TPS_0) * 100))
    latency_avg = latency_sum.value / target
    print(f"latency avg: {latency_avg}")
    print(f"interchain tx all num: {interalltx}")
    print(f"ts_src_avg: {ts_src_avg}")
    print(f"ts_rly01_avg: {ts_rly01_avg}")
    print(f"ts_inter_avg: {ts_inter_avg}")
    print(f"ts_rly02_avg: {ts_rly02_avg}")
    print(f"ts_dst_avg: {ts_dst_avg}")

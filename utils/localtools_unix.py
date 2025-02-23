from __future__ import annotations

__all__ = ["start_chainsimulator"]

import os
import argparse
import asyncio
import threading
import multiprocessing
import requests
import requests.adapters
import json
import time
import queue
import random
from loguru import logger
from concurrent.futures import ThreadPoolExecutor, wait as wait_futures
from unix_server.client.client_ms import ClientMS
from utils.request_helper import reqretry
from typing import Callable, List, Dict, Tuple
from chain_simulator.config.config import ConfigUnix
from chain_simulator.types.block import Block
from chain_simulator.types.transaction import TransactionIndexer, TranMemo
from chain_simulator.vm.store import BaseStore
from chain_simulator.mempool.mempool import SyncMemPool
from chain_simulator.blockchain.blockchain_p import (
    BlockchainStates,
    BlockchainMProc,
    BlockStorage,
)
from chain_simulator.service_unix.blockchain.blockchain_handlers import BlockchainHandler
from chain_simulator.service_unix.blockchain.transaction_handlers import TransactionHandler
# from chain_simulator.service.api_service import ApiService
from unix_server.service.api_service_ms import ApiService
from relayer_unix.connector.connector_unix import ConnectorUnix
from chain_simulator.service_unix.tool.response import StandardResponse


async def start_bcapi(
    setting: TestSetting,
    chain_num: int,
    chain_class: List[int], 
):
    cluster_size = 1
    assert len(chain_class) == 2, "chain class num must be 2"
    classes: List[str] = ["Ethereum"] * chain_class[0] + ["Tendermint"] * chain_class[1]
    hosts: List[List[str]] = [
        config.socket_paths for config in setting.para_configs
    ]

    configs_by_cluster = [
        setting.para_configs[i : i + cluster_size]
        for i in range(0, chain_num, cluster_size)
    ]
    cluster_num = len(configs_by_cluster)
    # Start parallel chains
    procs: List[multiprocessing.Process] = []
    stop_event = multiprocessing.Manager().Event()
    for i in range(cluster_num):
        proc_bc = multiprocessing.Process(
            target=start_chainsimulator,
            args=(
                configs_by_cluster[i],
                stop_event,
            ),
        )
        procs.append(proc_bc)

    for proc in procs:
        proc.start()
        print(f"proc.pid: {proc.pid}")
    for proc in procs:
        while proc.pid is None:
            await asyncio.sleep(1)

    # Start relay chain
    need_inter = setting.ccmode.lower() in ["tor", "aor"]
    inter_host = ""
    inter_proc = None
    if need_inter:
        inter_host = setting.inter_config.socket_paths
        inter_proc = multiprocessing.Process(
            target=start_chainsimulator, args=([setting.inter_config], stop_event)
        )
        inter_proc.start()
        while inter_proc.pid is None:
            await asyncio.sleep(1)
        print(f"inter proc.pid: {inter_proc.pid}")

    return procs, inter_proc, stop_event, inter_host, hosts, classes

async def start_bcapi_thread(
    setting: TestSetting,
    chain_num: int,
    chain_class: List[int], 
):
    cluster_size = 1
    assert len(chain_class) == 2, "chain class num must be 2"
    classes: List[str] = ["Ethereum"] * chain_class[0] + ["Tendermint"] * chain_class[1]
    hosts: List[List[str]] = [
        config.socket_paths for config in setting.para_configs
    ]

    configs_by_cluster = [
        setting.para_configs[i : i + cluster_size]
        for i in range(0, chain_num, cluster_size)
    ]
    cluster_num = len(configs_by_cluster)
    # Start parallel chains
    procs: List[threading.Thread] = []
    stop_event = threading.Event()
    for i in range(cluster_num):
        proc_bc = threading.Thread(
            target=start_chainsimulator,
            args=(
                configs_by_cluster[i],
                stop_event,
            ),
        )
        procs.append(proc_bc)

    for proc in procs:
        proc.start()
        # print(f"proc.pid: {proc.pid}")
    for proc in procs:
        while not proc.is_alive():
            await asyncio.sleep(1)

    # Start relay chain
    need_inter = setting.ccmode.lower() in ["tor", "aor"]
    inter_host = ""
    inter_proc = None
    if need_inter:
        inter_host = setting.inter_config.socket_paths
        inter_proc = threading.Thread(
            target=start_chainsimulator, args=([setting.inter_config], stop_event)
        )
        inter_proc.start()
        while not inter_proc.is_alive():
            await asyncio.sleep(1)
        # print(f"inter proc.pid: {inter_proc.pid}")

    return procs, inter_proc, stop_event, inter_host, hosts, classes


async def send_tx_chain(
    setting: TestSetting, paraid: int, socket_paths: List[str], classes: List[str]
):
    xtxnum = int(setting.xtxratio * setting.txnum)
    dsts = [-1] * (setting.txnum - xtxnum) + [1] * xtxnum
    dsts = random.sample(dsts, len(dsts))
    for i in range(len(dsts)):
        if dsts[i] == 1:
            x = None
            while True:
                x = random.randint(0, setting.chainnum - 1) 
                if x != paraid: 
                    break
            assert x is not None
            dsts[i] = x
    url_send_tx = f"/send_tx"
    client = ClientMS(socket_paths=socket_paths)
    # print(f"start sendtx to chain({paraid}), {dsts}")
    cnt = 0
    for idx in range(setting.txnum):
        if dsts[idx] >= 0:  
            dstid = int(dsts[idx])
            memo = {"type": TranMemo.CTXSRC, "dst": dsts[idx]}
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
            cnt += 1
        else:
            memo = {"type": "TX"}
            memo["ts"] = {"init": time.time()}  # type: ignore
            data = {
                "tx": {
                    "sender": f"send/{paraid}/{idx}",
                    "to": "base",
                    "data": json.dumps({"arguments": [f"a{idx}", idx]}),
                    "memo": json.dumps(memo),
                }
            }
        resp = client.post(url=url_send_tx, params=data)
        assert resp.code == 200, f"send tx failed: {resp.to_str()}"
        if idx % 20 == 0:
            print(f"sendtx to {paraid}: {idx}, time: {time.time()}")
        # await asyncio.sleep(0.01)
    client.close()
    print(f"sendtx to {paraid} finished! count: {cnt}")


async def send_tx_proc(setting: TestSetting, hosts: List[str], classes: List[str]):
    def main(paraid, host, classes):
        asyncio.run(send_tx_chain(setting, paraid, host, classes))

    procs: List[multiprocessing.Process] = []
    for paraid, host in enumerate(hosts):
        proc = multiprocessing.Process(target=main, args=(paraid, host, classes))
        procs.append(proc)

    for proc in procs:
        proc.start()

    for proc in procs:
        while proc.is_alive():
            await asyncio.sleep(2)
        proc.join()


async def listen_stop(stop_event: threading.Event, obj):
    logger.debug(f"listen stop event, obj: {obj}, stop_event: {stop_event}")
    while not stop_event.is_set():
        await asyncio.sleep(1)
    logger.debug(f"stop event set, stop {obj}")
    obj.stop()


async def main(
    stop_event: threading.Event,
    obj,
    func: Callable,
    *funcargs,
):
    task_listen = asyncio.create_task(listen_stop(stop_event, obj))
    await asyncio.sleep(0.01)
    await func(*funcargs)
    while not task_listen.done():
        await asyncio.sleep(0.05)
    


def start_api(stop_event: threading.Event, config: ConfigUnix, bcstates: BlockchainStates):
    api = ApiService(
        handlers=[BlockchainHandler, TransactionHandler], 
        socket_paths=config.socket_paths, 
        max_workers=config.max_workers, 
        max_conns=config.max_conns
    )
    args = {"bcstates": bcstates}
    asyncio.run(main(stop_event, api, api.run_app, args))


def start_bc(stop_event: threading.Event, config: ConfigUnix, bcstates: BlockchainStates):
    bcmp = BlockchainMProc(config=config, bc_status_manager=bcstates)
    asyncio.run(main(stop_event, bcmp, bcmp.start))


def start_chainsimulator(
    configs: List[ConfigUnix],
    stop_event: threading.Event,
):
    """
    start multi (bc, api)s with configs
    and pass stop_event to stop (bc, api)
    """
    threads: List[threading.Thread] = []
    for config in configs:
        block_storage = BlockStorage()
        transaction_indexer = TransactionIndexer()
        base_store = BaseStore()
        sync_mempool = SyncMemPool(maxsize=config.mempool_size)
        blockchain_states = BlockchainStates(
            mp=sync_mempool,
            blocks=block_storage,
            store=base_store,
            txindexer=transaction_indexer,
            config=config,
        )

        proc_bc = threading.Thread(
            target=start_bc, args=(stop_event, config, blockchain_states)
        )
        proc_api = threading.Thread(
            target=start_api,
            args=(
                stop_event,
                config,
                blockchain_states,
            ),
        )

        proc_bc.start()
        proc_api.start()

        threads.append(proc_bc)
        threads.append(proc_api)

    for thread in threads:
        thread.join()


def check(
    idx: int,
    socket_paths: List[str],
    target: int,
    val,
    min_init,
    max_last_commit,
    latency_sum,
    ctxs: multiprocessing.Queue,
):
    print(f"begin check chain({idx})...")
    tempctxs = []
    assert isinstance(socket_paths, List)
    assert all(isinstance(path, str) for path in socket_paths )
    assert isinstance(target, int)
    client = ClientMS(socket_paths=socket_paths)
    url = f"/query_block_number"
    r = client.get(url, {})
    r = StandardResponse.from_str(r.msg)
    bn = int(r.msg)
    i = 1
    starttime = 0
    print(f"check chain({idx})...")
    while True:
        if i > bn:
            while True:
                url = f"/query_block_number"
                r = client.get(url, {})
                r = StandardResponse.from_str(r.msg)
                bn = int(r.msg)
                if i <= bn:
                    break
                time.sleep(5)
        url_block = f"/query_block"
        r = client.get(url_block, {'bn': i})
        r = StandardResponse.from_str(r.msg)
        blk: dict = json.loads(r.msg)
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
                # if starttime == 0:
                #     starttime = time.time()
                # if time.time() - starttime < 20:
                #     print(f"val.value: {val.value}")
                # else:
                #     break
        i += 1
        print(f"val.value: {val.value}, target: {target}, current height: {i-1}")
    client.close()
    for item in tempctxs:
        ctxs.put(item)



def wait_check(hosts: List[str], target: int):
    print("wait_check...")
    manager = multiprocessing.Manager()
    check_procs = []
    val = multiprocessing.Value("i", 0)
    min_init = multiprocessing.Value("d", time.time() * 2)
    max_last_commit = multiprocessing.Value("d", 0)
    latency_sum = multiprocessing.Value("d", 0)
    ctxs = manager.Queue()
    print("ctxs = manager.Queue()")
    for idx, host in enumerate(hosts):
        proc = multiprocessing.Process(
            target=check,
            args=(idx, host, target, val, min_init, max_last_commit, latency_sum, ctxs),
        )
        check_procs.append(proc)
    print(f"check procs length: {len(check_procs)}")
    for proc in check_procs:
        proc.start()
    for proc in check_procs:
        proc.join()
    # (ctxs, target, min_init, max_last_commit, latency_sum)
    return ctxs, target, min_init.value, max_last_commit.value, latency_sum.value  # type: ignore


async def set_paraid(client: ClientMS, host: str, paraid: int):
    url_set_id = f"/send_tx"
    memo = {"type": "TX"}
    data = {
        "tx": {
            "sender": f"send/{paraid}/set",
            "to": "lightclient",
            "data": json.dumps({"func": "set_paraid", "arguments": [paraid]}),
            "memo": json.dumps(memo),
        }
    }
    resp = client.post(url_set_id, data)
    assert resp.code == 200, f"set paraid failed: {resp.to_str()}"
    


async def set_paratype(client: ClientMS, host: str, paratype: str):
    url_set_type = f"/send_tx"
    memo = {"type": "TX"}
    data = {
        "tx": {
            "sender": f"send/{paratype}/set",
            "to": "lightclient",
            "data": json.dumps({"func": "set_paratype", "arguments": [paratype]}),
            "memo": json.dumps(memo),
        }
    }
    resp = client.post(url_set_type, data)
    assert resp.code == 200, f"set paratype failed: {resp.to_str()}"


def create_multi_clients(socket_paths: List[List[str]]) -> List[ClientMS]:
    def create_client(socket_path: List[str]):
        return ClientMS(socket_paths=socket_path)
    with ThreadPoolExecutor(max_workers=30) as executor:
        clients = list(executor.map(create_client, socket_paths))
    return clients

def close_multi_clients(clients: List[ClientMS]):
    with ThreadPoolExecutor(max_workers=30) as executor:
        futures = [executor.submit(client.close) for client in clients]
        wait_futures(futures)

async def set_crossinfo(socket_paths: List[List[str]], pids: List[int], classes: List[str]):
    print(f"set_crossinfo: {socket_paths}, {pids}, {classes}")
    clients = create_multi_clients(socket_paths)
    cors = []
    for idx, (chainhost, chainid, chainclass) in enumerate(zip(socket_paths, pids, classes)):
        cor_setid = set_paraid(clients[idx], chainhost, chainid)
        cor_settype = set_paratype(clients[idx], chainhost, chainclass)
        cors.extend([cor_setid, cor_settype])
    await asyncio.gather(*cors)
    close_multi_clients(clients)

def stop_mining(client: ClientMS, socket_path: List[str]):
    print(f"stop mining: {socket_path}")
    url = f"/stop_mining"
    resp = client.post(url, {})
    assert resp.code == 200, f"stop mining failed: {resp.to_str()}"


def stop_all_mining(socket_paths: List[List[str]]):
    clients = create_multi_clients(socket_paths)
    for idx, socket_path in enumerate(socket_paths):
        stop_mining(clients[idx], socket_path)
    close_multi_clients(clients)


async def start_mining(client: ClientMS, socket_path: List[str]):
    print(f"start mining: {socket_path}")
    url = f"/start_mining"
    resp = client.post(url, {})
    assert resp.code == 200, f"start mining failed: {resp.to_str()}"
    return resp


async def start_all_mining(socket_paths: List[List[str]]):
    clients = create_multi_clients(socket_paths)
    cors = []
    for idx, socket_path in enumerate(socket_paths):
        cor = start_mining(clients[idx], socket_path)
        cors.append(cor)
    await asyncio.gather(*cors)
    close_multi_clients(clients)

async def start_gen_xtx(client: ClientMS, socket_path: str):
    print(f"start gen xtx: {socket_path}")
    url = f"/start_gen_xtx"
    resp = client.post(url, {})
    assert resp.code == 200, f"start gen xtx failed: {resp.to_str()}"
    return resp


async def start_all_gen_xtx(socket_paths: List[List[str]]):
    cors = []
    clients = create_multi_clients(socket_paths)
    for idx, socket_path in enumerate(socket_paths):
        cor = start_gen_xtx(clients[idx], socket_path)
        cors.append(cor)
    await asyncio.gather(*cors)
    close_multi_clients(clients)

def stop_gen_xtx(client: ClientMS, socket_paths: List[str]):
    print(f"stop gen xtx: {socket_paths}")
    url = f"/stop_gen_xtx"
    resp = client.post(url, {})
    assert resp.code == 200, f"stop gen xtx failed: {resp.to_str()}"
    return resp


async def stop_all_gen_xtx(socket_paths: List[List[str]]):
    cors = []
    clients = create_multi_clients(socket_paths)
    for idx, socket_path in enumerate(socket_paths):
        cor = stop_gen_xtx(clients[idx], socket_path)
        cors.append(cor)
    await asyncio.gather(*cors)
    close_multi_clients(clients)


async def stop_proc_by_event(
    stop_event: threading.Event, procs: List[multiprocessing.Process]
):
    stop_event.set()
    for proc in procs:
        while proc.is_alive():
            await asyncio.sleep(1)
        proc.join()


async def listen_singlechain_workload(
    socket_paths: List[str],
    workloads: List[int],
    stop_event: threading.Event,
):
    url = f"/query_pool_count"
    client = ClientMS(socket_paths=socket_paths)
    print(f"listen chain({socket_paths}) workloads")
    while True:
        if stop_event.is_set():
            break
        resp = client.get(url, {})
        resp = StandardResponse.from_str(resp.msg)
        mpcount = int(resp.msg)
        workloads.append(mpcount)
        await asyncio.sleep(1)
    client.close()

def listen_workloads(
    hostsmap: Dict[str, Dict[int, List[str]]], workloads: dict, stop_event: threading.Event
):
    result: Dict[int, List[int]] = {}
    allitems = [
        (chainid, chainhost)
        for chainid, chainhost in list(hostsmap["para"].items())
        + list(hostsmap.get("inter", {}).items())
    ]

    async def listen_async():
        cors = []
        for chainid, chainhost in allitems:
            result[chainid] = []
            cors.append(
                listen_singlechain_workload(
                    socket_paths=chainhost,
                    workloads=result[chainid],
                    stop_event=stop_event,
                )
            )
        await asyncio.gather(*cors)

    asyncio.run(listen_async())
    for chainid, _ in allitems:
        workloads[chainid] = result[chainid]


def listen_workloads_proc(
    socket_paths: Dict[str, Dict[int, List[str]]]
) -> Tuple[multiprocessing.Process, Dict, threading.Event]:
    manager = multiprocessing.Manager()
    workloads = manager.dict()
    stop_event = manager.Event()
    proc = multiprocessing.Process(
        target=listen_workloads, args=(socket_paths, workloads, stop_event)
    )
    proc.start()
    return proc, workloads, stop_event


def analysis_tor(memos: List[dict]) -> dict:
    ts_src = []
    ts_rly = []
    ts_dst = []
    for memo in memos:
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
    return {
        "ts_src_avg": ts_src_avg,
        "ts_rly_avg": ts_rly_avg,
        "ts_dst_avg": ts_dst_avg,
    }


def analysis_nor(memos: List[dict]) -> dict:
    ts_src = []
    ts_rly = []
    ts_dst = []
    for memo in memos:
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
    return {
        "ts_src_avg": ts_src_avg,
        "ts_rly_avg": ts_rly_avg,
        "ts_dst_avg": ts_dst_avg,
    }


def analysis_aor(memos: List[dict]) -> dict:
    ts_src = []
    ts_rly01 = []
    ts_inter = []
    ts_rly02 = []
    ts_dst = []
    for memo in memos:
        ts = memo["ts"]
        ts_src.append(ts["commit"][0] - ts["init"])
        rly = ts["relayer"]
        ts_rly01.append(rly[2][1] - rly[0][1])
        ts_inter.append(ts["commit"][1] - rly[2][1])
        ts_rly02.append(rly[5][1] - rly[3][1])
        ts_dst.append(ts["commit"][2] - rly[5][1])
    ts_src_avg = sum(ts_src) / len(ts_src)
    ts_rly01_avg = sum(ts_rly01) / len(ts_rly01)
    ts_inter_avg = sum(ts_inter) / len(ts_inter)
    ts_rly02_avg = sum(ts_rly02) / len(ts_rly02)
    ts_dst_avg = sum(ts_dst) / len(ts_dst)
    return {
        "ts_src_avg": ts_src_avg,
        "ts_rly01_avg": ts_rly01_avg,
        "ts_inter_avg": ts_inter_avg,
        "ts_rly02_avg": ts_rly02_avg,
        "ts_dst_avg": ts_dst_avg,
    }


def analysis(
    setting: TestSetting,
    ctxs: queue.Queue,
    interalltx: int,
    interdur: float,
    max_last_commit: float,
    min_init: float,
    latency_sum: float,
    start_deal_time: float,
    end_deal_time: float,
    workloads: Dict[int, List[int]],
):
    memos = []
    while not ctxs.empty():
        memo = ctxs.get()
        memos.append(memo)
    partial_data = ModeChoices.analysis(mode=setting.ccmode, memos=memos)

    target = setting.xtx_target()
    tps = target / (max_last_commit - min_init)
    latency_avg = latency_sum / target

    # 写 workloads
    json.dump(workloads, open(setting.workload_filepath, "w"))

    data = {
        "ccmode": setting.ccmode,
        "para_num": setting.chainnum,
        "xtx_ratio": setting.xtxratio,
        "interalltxs": interalltx,
        "interdur": interdur,
        "tps": tps,
        "latency_avg": latency_avg,
        "workload_file": setting.workload_filepath,
        "real time cost": max_last_commit - min_init,
        "deal time cost": end_deal_time - start_deal_time,
    }
    data.update(partial_data)

    # 写其他指标
    json.dump(data, open(setting.indicate_filepath, "w"))


class ModeChoices:
    __analysis_choices = {
        "tor": analysis_tor,
        "nor": analysis_nor,
        "aor": analysis_aor,
    }

    @staticmethod
    def analysis(mode: str, memos: List[dict]):
        assert isinstance(mode, str)
        mode = mode.lower()
        assert mode in ModeChoices.__analysis_choices, "invalid"
        return ModeChoices.__analysis_choices[mode](memos=memos)


async def query_inter_workload(socket_paths: List[str]) -> Tuple[int, float]:
    cnct = ConnectorUnix(socket_paths=socket_paths)
    maxbn = await cnct.query_block_number()
    txnums = 0
    cors = [cnct.query_block(i) for i in range(1, maxbn + 1)]
    blocks = await asyncio.gather(*cors)
    blk0 = min(blocks, key=lambda x: x.timestamp)
    blk1 = max(blocks, key=lambda x: x.timestamp)
    txnums = sum(len(block.txs) for block in blocks)
    return txnums, float(blk1.timestamp) - float(blk0.timestamp)


class TestSetting:
    ccmode = ""
    output_indicate_dir = "./locals_unix/output/indicates"
    output_workload_dir = "./locals_unix/output/workloads"
    txnum = 10
    xtxratio = 1.0
    chainnum = 3
    baseport = 12000
    para_config_bs = 100
    para_config_bi = 2
    para_config_mp = 0
    inter_config_bs = 1000
    inter_config_bi = 2
    inter_config_mp = 0
    socket_num_in_each_server = 1 
    max_workers = 30
    max_conns = None

    @classmethod
    def new(cls, cmdargs) -> TestSetting:
        cls.ccmode = cmdargs.ccmode
        assert cls.ccmode in ["ToR", "NoR", "AoR"]
        cls.output_indicate_dir = cmdargs.output_indicate_dir
        cls.output_workload_dir = cmdargs.output_workload_dir
        assert os.path.exists(
            cls.output_indicate_dir
        ), f"dir({cls.output_indicate_dir}) not exists"
        assert os.path.exists(
            cls.output_workload_dir
        ), f"dir({cls.output_workload_dir}) not exists"
        cls.xtxratio = cmdargs.xtxratio
        cls.chainnum = cmdargs.chainnum
        cls.txnum = cmdargs.txnum
        cls.baseport = cmdargs.baseport
        cls.workload_filepath = os.path.join(
            cls.output_workload_dir,
            f"{cls.ccmode}-{cls.chainnum}-{cls.txnum}-{int(cls.xtxratio*100)}.json",
        )
        cls.indicate_filepath = os.path.join(
            cls.output_indicate_dir,
            f"{cls.ccmode}-{cls.chainnum}-{cls.txnum}-{int(cls.xtxratio*100)}.json",
        )
        cls.para_config_bs = cmdargs.para_config_bs
        cls.para_config_bi = cmdargs.para_config_bi
        cls.para_config_mp = cmdargs.para_config_mp
        cls.inter_config_bs = cmdargs.inter_config_bs
        cls.inter_config_bi = cmdargs.inter_config_bi
        cls.inter_config_mp = cmdargs.inter_config_mp
        cls.socket_num_in_each_server = cmdargs.socket_num_in_each_server
        cls.max_workers = cmdargs.max_workers
        cls.max_conns = cmdargs.max_conns
        cls.para_configs = [
            ConfigUnix(
                block_size=cls.para_config_bs,
                block_interval=cls.para_config_bi,
                mempool_size=cls.para_config_mp,
                api_port=cls.baseport + i,
                socket_paths=[f"/tmp/socket_para_{i}_{j}.sock" for j in range(cls.socket_num_in_each_server)],
            )
            for i in range(cls.chainnum)
        ]
        cls.inter_config = ConfigUnix(
            block_size=cls.inter_config_bs,
            block_interval=cls.inter_config_bi,
            mempool_size=cls.inter_config_mp,
            api_port=cls.baseport + cls.chainnum,
            socket_paths=[f"/tmp/socket_inter_{i}.sock" for i in range(cls.socket_num_in_each_server)],
        )
        return cls()

    @classmethod
    def xtx_target(cls) -> int:
        return int(cls.chainnum * cls.txnum * cls.xtxratio * 1)

    @classmethod
    def xtx_selfgen_target(cls, targetblock: int) -> int:
        return sum(config.gen_xtx_num for config in cls.para_configs) * targetblock


def get_args():
    parser = argparse.ArgumentParser()
    parser.add_argument("--ccmode", type=str, required=True)
    parser.add_argument("--txnum", type=int, default=TestSetting.txnum)
    parser.add_argument("--xtxratio", type=float, default=TestSetting.xtxratio)
    parser.add_argument("--chainnum", type=int, default=TestSetting.chainnum)
    parser.add_argument("--baseport", type=int, default=TestSetting.baseport)
    parser.add_argument(
        "--output_indicate_dir", type=str, default=TestSetting.output_indicate_dir
    )
    parser.add_argument(
        "--output_workload_dir", type=str, default=TestSetting.output_workload_dir
    )
    parser.add_argument(
        "--para_config_bs", type=int, default=TestSetting.para_config_bs
    )
    parser.add_argument(
        "--para_config_bi", type=int, default=TestSetting.para_config_bi
    )
    parser.add_argument(
        "--para_config_mp", type=int, default=TestSetting.para_config_mp
    )
    parser.add_argument(
        "--inter_config_bs", type=int, default=TestSetting.inter_config_bs
    )
    parser.add_argument(
        "--inter_config_bi", type=int, default=TestSetting.inter_config_bi
    )
    parser.add_argument(
        "--inter_config_mp", type=int, default=TestSetting.inter_config_mp
    )
    parser.add_argument(
        "--socket_num_in_each_server", type=int, default=TestSetting.socket_num_in_each_server
    )
    parser.add_argument(
        "--max_workers", type=int, default=TestSetting.max_workers
    )
    parser.add_argument(
        "--max_conns", type=int, default=TestSetting.max_conns
    )
    return parser.parse_args()

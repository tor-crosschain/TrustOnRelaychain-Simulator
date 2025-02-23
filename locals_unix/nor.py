"""
Based on the file tests/test_nor_async_threading.py

Change the relayer construction mode to relayer/relayer/relayer_multiplex_async.py

1 chain maintains 1 relayer, and each relayer is responsible for 1 src and multiple dst
"""
import math
import time
import requests
import asyncio
import json
import threading
import random
import multiprocessing
import sys, os

sys.path.insert(0, os.path.abspath("."))
from multiprocessing.managers import BaseManager, NamespaceProxy
from typing import List
from relayer_unix.connector.connector_unix import ConnectorUnix
from relayer_unix.relayer.relayer_unix import RelayerUnix, Mode
from utils.localtools_unix import (
    start_all_mining,
    stop_all_mining,
    wait_check,
    set_crossinfo,
    stop_proc_by_event,
    listen_workloads_proc,
    analysis,
    TestSetting,
    get_args,
    send_tx_proc,
    query_inter_workload,
    start_bcapi,
    start_bcapi_thread
)


def build_and_start_relayers(hosts: List[List[str]]):
    async def create(srcid: int, dstid: int) -> ConnectorUnix:
        tgt_connector = await ConnectorUnix.new(
            host=hosts[dstid], sender=f"proc/{srcid}/{dstid}/dst"
        )
        assert tgt_connector.pid == dstid
        return tgt_connector

    async def create_relayers(paraid: int, hosts: List[List[str]]) -> RelayerUnix:
        lh = len(hosts)
        src_connector = await ConnectorUnix.new(
            socket_paths=hosts[paraid], sender=f"proc/{paraid}/{paraid}/src"
        )
        dst_cncts: List[ConnectorUnix] = []
        for i in range(lh):
            if paraid == i:
                continue
            dst_connector = await ConnectorUnix.new(
                socket_paths=hosts[i], sender=f"proc/{paraid}/{i}/dst"
            )
            dst_cncts.append(dst_connector)
        ma_relayer = RelayerUnix(src=src_connector, mode=Mode.MODENOR)
        for dst in dst_cncts:
            assert isinstance(dst, ConnectorUnix), f"dst type is {type(dst)}"
            ma_relayer.add_dst(dst)
        return ma_relayer

    async def listen_stop(relayer: RelayerUnix, stopevent: threading.Event):
        while not stopevent.is_set():
            await asyncio.sleep(1)
        relayer.stop()

    async def schedule(paraid: int, hosts: List[List[str]], stopevent: threading.Event):
        # create
        relayer: RelayerUnix = await create_relayers(paraid, hosts)

        # listen stop event
        cor = listen_stop(relayer, stopevent)
        task = asyncio.create_task(cor)
        await asyncio.sleep(0.01)

        # start
        await relayer.start_one_way()

        # check task stop
        await asyncio.sleep(0.5)
        assert task.done()

    def relay(paraid: int, hosts: List[List[str]], rly_proc_stop_event: threading.Event):
        asyncio.run(schedule(paraid, hosts, rly_proc_stop_event))

    lh = len(hosts)
    procs: List[multiprocessing.Process] = []
    rly_proc_stop_event = multiprocessing.Manager().Event()
    for idx in range(lh):
        proc = multiprocessing.Process(
            target=relay, args=(idx, hosts, rly_proc_stop_event)
        )
        procs.append(proc)

    for proc in procs:
        proc.start()

    return procs, rly_proc_stop_event


async def test_nor_async(setting: TestSetting):
    """Test cross-chain interactions between chain_num chains, using the two-way direct connection mode, so any two chains have a gateway;
    The number of transactions sent to each chain is fixed, the cross-chain transaction ratio is fixed, and the destination chain identifier of the cross-chain transaction is random;
    """
    assert setting.chainnum >= 2
    classone = setting.chainnum // 2
    classtwo = setting.chainnum - classone
    (
        procs_bcapi,
        _,
        stop_event_bcapi,
        _,
        hosts,
        classes,
    ) = await start_bcapi(
        setting=setting, chain_num=setting.chainnum, chain_class=[classone, classtwo]
    )
    # Wait for all procs to start
    await asyncio.sleep(3)

    # Check if the socket files have been created
    while True:
        if all(all(os.path.exists(socket_path) for socket_path in socket_paths) for socket_paths in hosts):
            break
        await asyncio.sleep(1)
    print("============check socket finished!============" + str(int(time.time())))

    # Set the chain id, chain type
    pids = list(range(setting.chainnum))
    await set_crossinfo(socket_paths=hosts, pids=pids, classes=classes)
    print("============set_crossinfo finished!============" + str(int(time.time())))

    # Wait for each chain to pack the set paraid/paratype transaction
    await asyncio.sleep(setting.para_configs[0].block_interval * 2)

    # Stop mining
    await stop_all_mining(hosts)
    print("============stop all mining finished!============" + str(int(time.time())))

    # Build and start relayer, each chain's relayers run in an async process
    hostsmap = {"para": {}, "inter": {}}
    hostsmap["para"] = {idx: host for idx, host in enumerate(hosts)}
    rly_procs, rly_stop_event = build_and_start_relayers(hosts)
    await asyncio.sleep(1)
    print("============start relayers finished!============" + str(int(time.time())))

    # Listen to the chain load
    proc_workload, workloads, stop_event_workload = listen_workloads_proc(hostsmap)

    # Start timing
    start_deal_time = time.perf_counter()

    # Start mining
    await start_all_mining(hosts)
    print("============start all mining finished!============" + str(int(time.time())))

    # Send transactions to each chain in parallel
    await send_tx_proc(setting, hosts, classes)
    print("============process sendtx finished!============" + str(int(time.time())))

    # Check if the number of transactions with memo.type == CTX-DST on all chains is the same as the cross-chain number
    (ctxs, _, min_init, max_last_commit, latency_sum) = wait_check(
        hosts, target=setting.xtx_target()
    )
    print("============wait check finished!============" + str(int(time.time())))

    # Stop listening to the chain load
    await stop_proc_by_event(stop_event_workload, [proc_workload])
    workloads = {key: value for key, value in workloads.items()}

    # End timing
    end_deal_time = time.perf_counter()

    # Close relayer
    await stop_proc_by_event(rly_stop_event, rly_procs)
    print("============close relayer!============" + str(int(time.time())))

    # Close blockchain and service
    await stop_proc_by_event(stop_event_bcapi, procs_bcapi)
    print("============close bcs and api servs!============" + str(int(time.time())))

    analysis(
        setting=setting,
        ctxs=ctxs,
        interalltx=0,
        interdur=0,
        max_last_commit=max_last_commit,
        min_init=min_init,
        latency_sum=latency_sum,
        start_deal_time=start_deal_time,
        end_deal_time=end_deal_time,
        workloads=workloads,
    )


if __name__ == "__main__":
    cmdargs = get_args()
    test_setting = TestSetting.new(cmdargs)
    starttime = time.perf_counter()
    asyncio.run(test_nor_async(setting=test_setting))
    endtime = time.perf_counter()
    print(f"time cost: {endtime-starttime}")

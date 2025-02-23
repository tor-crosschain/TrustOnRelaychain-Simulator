import sys, os

sys.path.insert(0, os.path.abspath("."))
import time
import asyncio
import json
import threading
import multiprocessing
from locals.workload_ratio_analysis.utils.workload_tools import update_basic_setting
from utils.localtools import (
    wait_check,
    set_crossinfo,
    stop_all_mining,
    start_all_mining,
    stop_proc_by_event,
    TestSetting,
    listen_workloads_proc,
    query_inter_workload,
    analysis,
    get_args,
    start_bcapi,
    start_all_gen_xtx,
)
from typing import Tuple, List, Dict
from chain_simulator.types.transaction import TranMemo
from relayer.connector.async_connector import AsyncConnector
from relayer.relayer.relayer import Mode
from relayer.relayer.relayer_multiplex_async import MultiplexAsyncRelayer


def build_and_start_relayers(hostsmap: Dict[str, Dict[int, str]]):
    """
    AoR mode, 1 relay chain connects multiple parallel chains, each parallel chain only connects to the relay chain
    """

    async def create(
        src: Tuple[int, str, bool],
        dst: Tuple[int, str, bool],
    ) -> AsyncConnector:
        tgt_connector = await AsyncConnector.new(
            host=dst[1], sender=f"proc/{src[0]}/{dst[0]}/dst", isinter=dst[2]
        )
        assert tgt_connector.pid == dst[0]
        return tgt_connector

    async def create_relayers(
        ownerchainid: int,
        ownerchainhost: str,
        isinter: bool,
        ends: List[Tuple[int, str, bool]],
    ) -> MultiplexAsyncRelayer:
        cors = []
        src_connector = await AsyncConnector.new(
            host=ownerchainhost,
            sender=f"proc/{ownerchainid}/{ownerchainid}/src",
            isinter=isinter,
        )
        for chainid, chainhost, interflag in ends:
            if chainid == ownerchainid:
                continue
            cor = create(
                (ownerchainid, ownerchainhost, isinter), (chainid, chainhost, interflag)
            )
            cors.append(cor)
        dst_cncts = await asyncio.gather(*cors)
        ma_relayer = MultiplexAsyncRelayer(src=src_connector, mode=Mode.MODEAOR)
        for dst in dst_cncts:
            assert isinstance(dst, AsyncConnector), f"dst type is {type(dst)}"
            ma_relayer.add_dst(dst)
        return ma_relayer

    async def listen_stop(relayer: MultiplexAsyncRelayer, stopevent: threading.Event):
        while not stopevent.is_set():
            await asyncio.sleep(1)
        relayer.stop()

    async def schedule(
        ownerchainid: int,
        ownerchainhost: str,
        isinter: bool,
        ends: List[Tuple[int, str, bool]],
        stopevent: threading.Event,
    ):
        # create
        relayer: MultiplexAsyncRelayer = await create_relayers(
            ownerchainid, ownerchainhost, isinter, ends
        )

        # listen stop event
        cor = listen_stop(relayer, stopevent)
        task = asyncio.create_task(cor)
        await asyncio.sleep(0.01)

        # start
        await relayer.start_one_way()

        # check task stop
        await asyncio.sleep(0.5)
        assert task.done()

    def relay(
        ownerchainid: int,
        ownerchainhost: str,
        isinter: bool,
        ends: List[Tuple[int, str, bool]],
        rly_proc_stop_event: threading.Event,
    ):
        asyncio.run(
            schedule(ownerchainid, ownerchainhost, isinter, ends, rly_proc_stop_event)
        )

    procs: List[multiprocessing.Process] = []
    rly_proc_stop_event = multiprocessing.Manager().Event()

    # Start the gateway of the parallel chain
    isinter = False
    dsts_inter: List[Tuple[int, str, bool]] = [
        (*item, True) for item in hostsmap["inter"].items()
    ]  
    for paraid, host in hostsmap["para"].items():
        proc = multiprocessing.Process(
            target=relay,
            args=(
                paraid,
                host,
                isinter,
                dsts_inter,
                rly_proc_stop_event,
            ),
        )
        procs.append(proc)

    # Start the gateway of the relay chain
    inter_id = list(hostsmap["inter"].keys())[0]
    inter_host = hostsmap["inter"][inter_id]
    isinter = True
    dsts_para: List[Tuple[int, str, bool]] = [
        (*item, False) for item in hostsmap["para"].items()
    ]
    inter_proc = multiprocessing.Process(
        target=relay,
        args=(
            inter_id,
            inter_host,
            isinter,
            dsts_para,
            rly_proc_stop_event,
        ),
    )

    for proc in procs:
        proc.start()
    inter_proc.start()

    return inter_proc, procs, rly_proc_stop_event


async def check_inter_ctx_number(interhost: str, target: int):
    """Check if the number of cross-chain transactions on the relay chain is equal to target"""
    cnct = AsyncConnector(host=interhost)
    maxbn = await cnct.query_block_number()
    count = 0
    for bn in range(1, maxbn + 1):
        block = await cnct.query_block(bn)
        txs = block.txs
        for tx in txs:
            memo = json.loads(tx.memo)
            if memo["type"] == TranMemo.CTXINTER:
                count += 1
    assert target == count


async def test_aor_async(setting: TestSetting):
    """Test cross-chain interactions between chain_num chains, using the AoR cross-chain mode;
    There is 1 relay chain in the system;
    There are n parallel chains in the system;
    The parallel chains and the relay chain interact (need to synchronize block headers and cross-chain transactions);
    The number of transactions sent to each chain is fixed, the cross-chain transaction ratio is fixed, and the destination chain identifier of the cross-chain transaction is random;
    """
    assert setting.chainnum >= 2
    classone = setting.chainnum // 2
    classtwo = setting.chainnum - classone

    # Update setting, including: config for generating cross-chain transactions, data generation path
    update_basic_setting(setting)

    (
        procs_bcapi,
        inter_proc_bcapi,
        stop_event_bcapi,
        inter_host,
        hosts,
        classes,
    ) = await start_bcapi(
        setting=setting, chain_num=setting.chainnum, chain_class=[classone, classtwo]
    )
    await asyncio.sleep(3)
    assert inter_proc_bcapi is not None
    assert inter_host != ""

    # Set the pid of the relay chain and the parallel chain, and the chain type (the relay chain is fixed to tendermint)
    inter_pid = 30000
    await set_crossinfo(
        hosts=[inter_host] + hosts,
        pids=[inter_pid] + list(range(setting.chainnum)),
        classes=["Tendermint"] + classes,
    )
    print("============set_crossinfo finished!============" + str(int(time.time())))
    # Wait for each chain to pack the set paraid/paratype transaction
    await asyncio.sleep(setting.para_configs[0].block_interval * 2)

    # Stop mining
    await stop_all_mining([inter_host] + hosts)
    print("============stop all mining finished!============" + str(int(time.time())))

    # Build and start relayer, each chain's relayers run in an async process
    hostsmap = {"para": {}, "inter": {}}
    hostsmap["para"] = {idx: host for idx, host in enumerate(hosts)}
    hostsmap["inter"] = {inter_pid: inter_host}
    inter_proc, rly_procs, rly_stop_event = build_and_start_relayers(hostsmap)
    await asyncio.sleep(1)
    print("============start relayers finished!============" + str(int(time.time())))

    # Listen to the chain load
    proc_workload, workloads, stop_event_workload = listen_workloads_proc(hostsmap)

    # Start timing
    start_deal_time = time.perf_counter()

    # Start blockchain mining
    await start_all_mining([inter_host] + hosts)
    print("============start all mining finished!============" + str(int(time.time())))

    # Start automatic generation of cross-chain transactions
    await start_all_gen_xtx(hosts)
    print(
        "============start generate xtx finished!============" + str(int(time.time()))
    )

    # Check if the number of transactions with memo.type == CTX-DST on all chains is the same as the cross-chain number
    (ctxs, target, min_init, max_last_commit, latency_sum) = wait_check(
        hosts, target=setting.xtx_selfgen_target(targetblock=20)
    )
    print("============wait check finished!============" + str(int(time.time())))

    # Stop listening to the chain load
    await stop_proc_by_event(stop_event_workload, [proc_workload])
    workloads = {key: value for key, value in workloads.items()}

    # Stop timing
    end_deal_time = time.perf_counter()

    # Close relayer
    await stop_proc_by_event(rly_stop_event, [inter_proc] + rly_procs)
    print("============close relayer!============" + str(int(time.time())))

    # Get the total number of transactions on the relay chain
    interalltx, interdur = await query_inter_workload(inter_host)

    # Close blockchain and service
    await stop_proc_by_event(stop_event_bcapi, [inter_proc_bcapi] + procs_bcapi)
    print("============close bcs and api servs!============" + str(int(time.time())))

    analysis(
        setting=setting,
        ctxs=ctxs,
        interalltx=interalltx,
        interdur=interdur,
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
    asyncio.run(test_aor_async(setting=test_setting))
    endtime = time.perf_counter()
    print(f"time cost: {endtime-starttime}")

from __future__ import annotations
import sys, os

sys.path.insert(0, os.path.abspath("."))
import time
import asyncio
import threading
import multiprocessing
from loguru import logger
from typing import Tuple, List, Optional, Dict
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
from relayer_unix.connector.connector_unix import ConnectorUnix
from relayer_unix.relayer.relayer_unix import RelayerUnix, Mode, ToRRelayerType

multiprocessing.set_start_method('fork')

async def build_and_start_relayers(hostsmap: Dict[str, Dict[int, List[str]]]):
    """
    ToR mode, 1 relay chain connects multiple parachains, each parachain only connects to the relay chain
    """

    async def create(
        src: Tuple[int, List[str], bool],
        dst: Tuple[int, List[str], bool],
    ) -> ConnectorUnix:
        tgt_connector = await ConnectorUnix.new(
            socket_paths=dst[1], sender=f"proc/{src[0]}/{dst[0]}/dst", isinter=dst[2]
        )
        assert tgt_connector.pid == dst[0]
        return tgt_connector

    async def create_relayers(
        ownerchainid: int,
        ownerchainhost: List[str],
        isinter: bool,
        ends: List[Tuple[int, str, bool]],
        **kwargs,
    ) -> RelayerUnix:

        src_connector = await ConnectorUnix.new(
            socket_paths=ownerchainhost,
            sender=f"proc/{ownerchainid}/{ownerchainid}/src",
            isinter=isinter,
        )
        ispap = not isinter
        dst_cncts: List[ConnectorUnix] = []
        for chainid, chainhost, interflag in ends:
            if chainid == ownerchainid:
                continue
            dst_connector = await ConnectorUnix.new(
                socket_paths=chainhost, sender=f"proc/{ownerchainid}/{chainid}/dst", isinter=interflag
            )
            dst_cncts.append(dst_connector)
            ispap &= not interflag
        inter_cnct: Optional[ConnectorUnix] = None
        if ispap:
            inter_host = kwargs["inter_connector"]
            inter_cnct = await ConnectorUnix.new(
                socket_paths=inter_host, sender=f"proc/{inter_id}/{inter_id}/dst", isinter=True
            )
        ma_relayer = RelayerUnix(
            src=src_connector,
            mode=Mode.MODETOR,
            inter=inter_cnct,  # type: ignore
            rlytp=ToRRelayerType.PAP if ispap else ToRRelayerType.PAR,  # type: ignore
        )
        for dst in dst_cncts:
            assert isinstance(dst, ConnectorUnix), f"dst type is {type(dst)}"
            ma_relayer.add_dst(dst)
        return ma_relayer

    async def listen_stop(relayer: RelayerUnix, stopevent: threading.Event):
        while not stopevent.is_set():
            await asyncio.sleep(1)
        relayer.stop()

    async def schedule(
        ownerchainid: int,
        ownerchainhost: List[str],
        isinter: bool,
        ends: List[Tuple[int, str, bool]],
        stopevent: threading.Event,
        **kwargs,
    ):
        # create
        relayer: RelayerUnix = await create_relayers(
            ownerchainid, ownerchainhost, isinter, ends, **kwargs
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
        ownerchainhost: List[str],
        isinter: bool,
        ends: List[Tuple[int, str, bool]],
        rly_proc_stop_event: threading.Event,
        **kwargs,
    ):
        asyncio.run(
            schedule(
                ownerchainid,
                ownerchainhost,
                isinter,
                ends,
                rly_proc_stop_event,
                **kwargs,
            )
        )

    procs: List[multiprocessing.Process] = []
    rly_proc_stop_event = multiprocessing.Event()

    # start the gateway of the parachain
    isinter = False
    dsts_inter: List[Tuple[int, str, bool]] = [
        (*item, True) for item in hostsmap["inter"].items()
    ]  # type: ignore # bool means isinter
    dsts_para: List[Tuple[int, str, bool]] = [
        (*item, False) for item in hostsmap["para"].items()
    ]  # type: ignore
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

    # start the gateway of the relay chain
    inter_id = list(hostsmap["inter"].keys())[0]
    inter_host = hostsmap["inter"][inter_id]
    isinter = True
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

    # start the gateway of the parachain
    isinter = False
    for paraid, host in hostsmap["para"].items():
        proc = multiprocessing.Process(
            target=relay,
            args=(paraid, host, isinter, dsts_para, rly_proc_stop_event),
            kwargs={"inter_connector": inter_host},
        )
        procs.append(proc)

    for proc in procs:
        proc.start()
    inter_proc.start()

    return inter_proc, procs, rly_proc_stop_event

async def build_and_start_relayers_thread(hostsmap: Dict[str, Dict[int, List[str]]]):
    """
    ToR mode, 1 relay chain connects multiple parachains, each parachain only connects to the relay chain
    """

    async def create(
        src: Tuple[int, List[str], bool],
        dst: Tuple[int, List[str], bool],
    ) -> ConnectorUnix:
        tgt_connector = await ConnectorUnix.new(
            socket_paths=dst[1], sender=f"proc/{src[0]}/{dst[0]}/dst", isinter=dst[2]
        )
        assert tgt_connector.pid == dst[0]
        return tgt_connector

    async def create_relayers(
        ownerchainid: int,
        ownerchainhost: List[str],
        isinter: bool,
        ends: List[Tuple[int, str, bool]],
        **kwargs,
    ) -> RelayerUnix:

        src_connector = await ConnectorUnix.new(
            socket_paths=ownerchainhost,
            sender=f"proc/{ownerchainid}/{ownerchainid}/src",
            isinter=isinter,
        )
        ispap = not isinter
        dst_cncts: List[ConnectorUnix] = []
        for chainid, chainhost, interflag in ends:
            if chainid == ownerchainid:
                continue
            dst_connector = await ConnectorUnix.new(
                socket_paths=chainhost, sender=f"proc/{ownerchainid}/{chainid}/dst", isinter=interflag
            )
            dst_cncts.append(dst_connector)
            ispap &= not interflag
        inter_cnct: Optional[ConnectorUnix] = None
        if ispap:
            inter_host = kwargs["inter_connector"]
            inter_cnct = await ConnectorUnix.new(
                socket_paths=inter_host, sender=f"proc/{inter_id}/{inter_id}/dst", isinter=True
            )
        ma_relayer = RelayerUnix(
            src=src_connector,
            mode=Mode.MODETOR,
            inter=inter_cnct,  # type: ignore
            rlytp=ToRRelayerType.PAP if ispap else ToRRelayerType.PAR,  # type: ignore
        )
        for dst in dst_cncts:
            assert isinstance(dst, ConnectorUnix), f"dst type is {type(dst)}"
            ma_relayer.add_dst(dst)
        return ma_relayer

    async def listen_stop(relayer: RelayerUnix, stopevent: threading.Event):
        while not stopevent.is_set():
            await asyncio.sleep(1)
        relayer.stop()

    async def schedule(
        ownerchainid: int,
        ownerchainhost: List[str],
        isinter: bool,
        ends: List[Tuple[int, str, bool]],
        stopevent: threading.Event,
        **kwargs,
    ):
        # create
        relayer: RelayerUnix = await create_relayers(
            ownerchainid, ownerchainhost, isinter, ends, **kwargs
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
        ownerchainhost: List[str],
        isinter: bool,
        ends: List[Tuple[int, str, bool]],
        rly_proc_stop_event: threading.Event,
        **kwargs,
    ):
        asyncio.run(
            schedule(
                ownerchainid,
                ownerchainhost,
                isinter,
                ends,
                rly_proc_stop_event,
                **kwargs,
            )
        )

    procs: List[threading.Thread] = []
    rly_proc_stop_event = threading.Event()

    # start the gateway of the parachain
    isinter = False
    dsts_inter: List[Tuple[int, str, bool]] = [
        (*item, True) for item in hostsmap["inter"].items()
    ]  # type: ignore # bool means isinter
    dsts_para: List[Tuple[int, str, bool]] = [
        (*item, False) for item in hostsmap["para"].items()
    ]  # type: ignore
    for paraid, host in hostsmap["para"].items():
        thread = threading.Thread(
            target=relay,
            args=(
                paraid,
                host,
                isinter,
                dsts_inter,
                rly_proc_stop_event,
            ),
        )
        procs.append(thread)

    # start the gateway of the relay chain
    inter_id = list(hostsmap["inter"].keys())[0]
    inter_host = hostsmap["inter"][inter_id]
    isinter = True
    inter_proc = threading.Thread(
        target=relay,
        args=(
            inter_id,
            inter_host,
            isinter,
            dsts_para,
            rly_proc_stop_event,
        ),
    )

    # start the gateway of the parachain
    isinter = False
    for paraid, host in hostsmap["para"].items():
        proc = threading.Thread(
            target=relay,
            args=(paraid, host, isinter, dsts_para, rly_proc_stop_event),
            kwargs={"inter_connector": inter_host},
        )
        procs.append(proc)

    for proc in procs:
        proc.start()
    inter_proc.start()

    return inter_proc, procs, rly_proc_stop_event


async def test_tor_async(setting: TestSetting):
    """Test cross-chain interactions between chain_num chains, using the ToR cross-chain mode
    There is 1 relay chain in the system;
    There are n parachains in the system;
    The parachain uses the PAP gateway (only responsible for synchronizing cross-chain transactions), and the parachain and relay chain use the PAR gateway (only responsible for synchronizing block headers);
    The number of transactions sent to each chain is fixed, the cross-chain transaction ratio is fixed, and the destination chain identifier of the cross-chain transaction is random;
    """
    assert setting.chainnum >= 2
    classone = setting.chainnum // 2
    classtwo = setting.chainnum - classone
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
    # print("ok")
    await asyncio.sleep(3)
    assert inter_proc_bcapi is not None
    assert inter_host != ""

    # check if the socket files have been created
    while True:
        if all(all(os.path.exists(socket_path) for socket_path in socket_paths) for socket_paths in hosts+[inter_host]):
            break
        await asyncio.sleep(1)
    print("============check socket finished!============" + str(int(time.time())))


    # set the pid of the relay chain and the parachain, the chain type (the relay chain is fixed to tendermint)
    inter_pid = 30000
    await set_crossinfo(
        socket_paths=[inter_host] + hosts,
        pids=[inter_pid] + list(range(setting.chainnum)),
        classes=["Tendermint"] + classes,
    )
    print("============set_crossinfo finished!============" + str(int(time.time())))
    # wait for each chain to pack the set paraid/paratype transaction
    await asyncio.sleep(setting.para_configs[0].block_interval * 2)

    # stop mining
    stop_all_mining([inter_host] + hosts)
    print("============stop all mining finished!============" + str(int(time.time())))

    
    # build and start relayer, each chain's relayer runs in an asynchronous process
    hostsmap = {"para": {}, "inter": {}}
    hostsmap["para"] = {idx: host for idx, host in enumerate(hosts)}
    hostsmap["inter"] = {inter_pid: inter_host}
    inter_proc, rly_procs, rly_stop_event = await build_and_start_relayers(hostsmap)
    await asyncio.sleep(1)
    print("============start relayers finished!============" + str(int(time.time())))

    # listen the workload
    proc_workload, workloads, stop_event_workload = listen_workloads_proc(hostsmap)

    # start timing (real processing time)
    start_deal_time = time.perf_counter()

    # start mining
    await start_all_mining([inter_host] + hosts)
    print("============start all mining finished!============" + str(int(time.time())))


    # send transactions to each chain in parallel
    # await send_tx(hosts, classes=classes)
    await send_tx_proc(setting, hosts, classes)
    print("============process sendtx finished!============" + str(int(time.time())))

    # check if the number of transactions with memo.type == CTX-DST on all chains is the same as the number of cross-chain transactions
    (ctxs, _, min_init, max_last_commit, latency_sum) = wait_check(
        hosts, target=setting.xtx_target()
    )
    print("============wait check finished!============" + str(int(time.time())))

    # stop listening the workload
    await stop_proc_by_event(stop_event_workload, [proc_workload])
    workloads = {key: value for key, value in workloads.items()}

    # stop timing (real processing time)
    end_deal_time = time.perf_counter()

    # close relayer
    await stop_proc_by_event(rly_stop_event, [inter_proc] + rly_procs)
    print("============close relayer!============" + str(int(time.time())))

    # get the total number of transactions on the relay chain
    interalltx, interdur = await query_inter_workload(inter_host)

    # close the blockchain and service
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
    asyncio.run(test_tor_async(test_setting))
    endtime = time.perf_counter()
    print(f"time cost: {endtime-starttime}")

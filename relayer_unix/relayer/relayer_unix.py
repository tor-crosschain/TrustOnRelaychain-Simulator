from __future__ import annotations
import time
import asyncio
import json
import multiprocessing
import traceback
import queue
from typing import List, Tuple, Dict, Optional
from utils.request_helper import ConnectionException
from relayer_unix.connector.connector_unix import ConnectorUnix
from chain_simulator.types.transaction import TranMemo
from chain_simulator.types.transaction import Transaction, TxStatus


def mark_tx(tx: Transaction, time_key: str):
    # mark the time of tx.memo, the time type is time_key
    assert isinstance(tx, Transaction)
    assert isinstance(time_key, str)
    relayer_key = "relayer"
    # time_key = f"relayer/{time_key}"
    now_time = time.time()
    memo: dict = json.loads(tx.memo)
    ts = memo.get("ts", {})
    if ts.get(relayer_key, None) is None:
        ts[relayer_key] = []
    ts[relayer_key].append((time_key, now_time))
    memo["ts"] = ts
    tx.memo = json.dumps(memo)


async def wait_stop(stop_event: asyncio.Event, queue: asyncio.Queue):
    while not stop_event.is_set():
        await asyncio.sleep(1)
    await queue.put(None)


class Mode:
    MODENOR = "mode-NoR"
    MODEAOR = "mode-AoR"
    MODETOR = "mode-ToR"

    @staticmethod
    def is_mode(mode: str) -> bool:
        return mode in (Mode.MODEAOR, Mode.MODENOR, Mode.MODETOR)


class ToRRelayerType:
    """In ToR mode, the type of the gateway"""

    PAR = 0  # the relayer between the relay chain and the parallel chain, only synchronize block headers
    PAP = 1  # the relayer between the parallel chains, only synchronize cross-chain transactions

    @staticmethod
    def is_relayertype(_type: int) -> bool:
        return _type in (ToRRelayerType.PAR, ToRRelayerType.PAP)


class DstTool:
    def __init__(
        self,
        connector: ConnectorUnix,
        queue_xtx_maxsize: int = 0,
        queue_header_maxsize: int = 0,
    ) -> None:
        assert isinstance(connector, ConnectorUnix)
        self.connector = connector
        self.stopped = False
        self.queue_xtx = asyncio.Queue(maxsize=queue_xtx_maxsize)
        self.queue_header = asyncio.Queue(maxsize=queue_header_maxsize)


class Dsts:
    def __init__(self) -> None:
        self.dsts: Dict[int, DstTool] = {}

    def store_connector(self, connector: ConnectorUnix) -> DstTool:
        assert isinstance(
            connector, ConnectorUnix
        ), f"connector must be AsyncConnector, but {type(connector)}"
        pid = connector.pid
        assert isinstance(pid, int), f"pid must be int, but {type(pid)}"
        assert pid not in self.dsts, f"pid({pid}) not in dsts"
        dstool = DstTool(connector)
        self.dsts[pid] = dstool
        return dstool

    def get_connector(self, pid: int) -> DstTool:
        # print(f"get_connector: {pid}")
        assert pid in self.dsts, f"pid({pid}) not in dsts({self.dsts.keys()})"
        return self.dsts.get(pid)

    def all_pids(self) -> List[int]:
        return list(self.dsts.keys())

    async def put_tx(self, tx: Transaction, dstid: int):
        # print(f"put_tx: {dstid}")
        assert isinstance(tx, Transaction), f"tx must be Transaction, but {type(tx)}"
        dst_cnct = self.get_connector(dstid)
        await dst_cnct.queue_xtx.put(tx)

    async def put_header(self, header: dict, dstid: int):
        # print(f"in put_header, dstid={dstid}")
        assert isinstance(header, dict), f"header must be dict, but {type(header)}"
        dst_cnct = self.get_connector(dstid)
        # print(f"after getconnector: {dstid}")
        await dst_cnct.queue_header.put(header)
    
    def close(self):
        for _, dstcnct in self.dsts.items():
            dstcnct.connector.close()


class RelayerUnix(object):
    def __init__(
        self,
        src: ConnectorUnix,
        # dst: AsyncConnector,
        mode: str,
        inter: ConnectorUnix = None,
        rlytp: ToRRelayerType = None,
    ) -> None:
        assert isinstance(src, ConnectorUnix)
        # assert isinstance(dst, AsyncConnector)
        self.src = src
        self.dsts: Dsts = Dsts()
        # self.dst = dst

        assert Mode.is_mode(mode), f"invalid mode({mode})"
        self.mode = mode
        self.rlytp = rlytp
        self.inter = inter
        if mode == Mode.MODETOR:
            # pap: whether the relayer is the relayer between the relay chain and the parallel chain
            # par: whether the relayer is the relayer between the parallel chains
            # pap and par can only have 1 true
            # if pap is true, then inter: AsyncConnector cannot be empty
            assert ToRRelayerType.is_relayertype(self.rlytp)
            if self.rlytp == ToRRelayerType.PAP:
                # If it is a gateway between parallel chains, inter must be assigned
                assert isinstance(self.inter, ConnectorUnix)
            # else:
            #     # if the relayer is the relayer between the relay chain and the parallel chain, then src and dst must have only 1 true
            #     assert self.src.isinter ^ self.dst.isinter
        else:
            # in AoR or NoR mode, rlytp cannot be set
            assert self.rlytp is None

        # starttime = time.time()
        # self.queue_header = asyncio.Queue()

        self.listen_event_stop = asyncio.Event()
        self.header_event_stop = asyncio.Event()
        self.xtx_event_stop = asyncio.Event()
        self.tasks_header: List[asyncio.Task] = []
        self.tasks_xtx: List[asyncio.Task] = []
        # print(f"create Event cost: {time.time()-starttime}")

    def add_dst(self, dst: ConnectorUnix):
        assert isinstance(dst, ConnectorUnix)
        assert (
            dst.pid != self.src.pid
        ), f"dst.pid({dst.pid}) cannot be equal src.pid({self.src.pid})"
        if self.mode == Mode.MODETOR and self.rlytp == ToRRelayerType.PAR:
            assert (self.src.isinter or dst.isinter) and (not self.src.isinter or not dst.isinter)
        dstool = self.dsts.store_connector(dst)
        task_header = asyncio.create_task(
            self.deal_header(dstool=dstool, inter=self.inter)
        )
        task_xtx = asyncio.create_task(self.deal_xtx(dstool=dstool, inter=self.inter))
        self.tasks_header.append(task_header)
        self.tasks_xtx.append(task_xtx)

    def is_xtx(self, tx: Transaction) -> bool:
        """
        according to whether the type of tx.memo is SRC-CTX or INTER-CTX
        """
        memo = json.loads(tx.memo)
        return memo.get("type") in [TranMemo.CTXSRC, TranMemo.CTXINTER]

    async def filter_header(self, header: dict):
        """filter header which should be transmitted to dst chain

        :param header: block header
        :type header: dict
        """
        dst_ids = []
        if self.mode == Mode.MODEAOR:
            if self.src.isinter:
                # if the source is inter, then it needs to forward to each parallel chain
                dst_ids += self.dsts.all_pids()
            else:
                # if the source is not inter, then it needs to be forwarded to the relay chain inter
                dst_ids += [30000]
        elif self.mode == Mode.MODENOR:
            dst_ids += self.dsts.all_pids()
        elif self.mode == Mode.MODETOR and self.rlytp == ToRRelayerType.PAR:
            # ToR mode, and also par type gateway
            if self.src.isinter:
                # if the source is inter, then it needs to forward to each parallel chain
                dst_ids += self.dsts.all_pids()
            else:
                # if the source is not inter, then it needs to be forwarded to the relay chain inter
                dst_ids += [30000]

        for pid in dst_ids:
            if pid != self.src.pid:
                # print(f"put header to pid({pid})")
                await self.dsts.put_header(header, pid)

    async def filter_txs(self, txs: List[Transaction]) -> int:
        """filter crosschain txs from all transactions in a block

        :param txs: transactions in a block
        :type txs: List[Transaction]
        """

        def parse_next_pid(xtx: Transaction) -> int:
            """parse next chain id from tx.memo
            AND update memo (this is not elegant)
            """
            memo: dict = json.loads(xtx.memo)
            xtxtype = memo["type"]
            # mode = memo["mode"]
            if self.mode == Mode.MODENOR:
                if xtxtype == TranMemo.CTXSRC:
                    memo.update({"type": TranMemo.CTXDST, "src": self.src.pid})
                    xtx.memo = json.dumps(memo)
                    return int(memo.get("dst", -1))
            elif self.mode == Mode.MODEAOR:
                if xtxtype == TranMemo.CTXSRC:
                    memo.update({"type": TranMemo.CTXINTER, "src": self.src.pid})
                    xtx.memo = json.dumps(memo)
                    return 30000
                elif xtxtype == TranMemo.CTXINTER:
                    memo.update({"type": TranMemo.CTXDST, "src": self.src.pid})
                    xtx.memo = json.dumps(memo)
                    return int(memo.get("dst", -1))
            elif self.mode == Mode.MODETOR and self.rlytp == ToRRelayerType.PAP:
                # In ToR mode, only pap type gateway needs to forward transactions
                if xtxtype == TranMemo.CTXSRC:
                    memo.update({"type": TranMemo.CTXDST, "src": self.src.pid})
                    xtx.memo = json.dumps(memo)
                    return int(memo.get("dst", -1))
            return -1

        if self.mode == Mode.MODETOR and self.rlytp == ToRRelayerType.PAR:
            # ToR mode, and also par type gateway, no need to forward cross-chain transactions
            return 0
        cnt = 0
        for tx in txs:
            if self.is_xtx(tx) and tx.status == TxStatus.SUCCESS:
                dst_id = parse_next_pid(tx)
                if dst_id == -1:
                    continue
                mark_tx(tx, time_key="listened")
                if dst_id == self.src.pid:
                    print(f"occur DUPLICATION: {self.src.pid}, {tx.memo}")
                await self.dsts.put_tx(tx, dst_id)
                cnt += 1
        return cnt

    async def listen_block(self):
        """
        listen latest block every 2 seconds and:
        1. put header to queue_header:Queue
        2. put successful xtx to queue_xtx:Queue
        """
        # only synchronize from the latest block header of src
        cur_height = await self.src.query_block_number()
        maxbn = cur_height - 1

        nextbn = maxbn + 1
        while not self.listen_event_stop.is_set():
            try:
                latestblock = await self.src.query_block(bn=nextbn)
                header = latestblock.header()
                await self.filter_header(header)
                xtx_cnt = await self.filter_txs(latestblock.txs)
                print(f"listen_block({nextbn}) ok, find xtx cnt:{xtx_cnt}")
                nextbn += 1
                await asyncio.sleep(1)
            except ConnectionException as e:
                print(f"listen_block({nextbn}) connection warning: {str(e)}")
                await asyncio.sleep(2)  # TODO read sleep time from config
            except Exception as e:
                if "cannot find block" in str(e):
                    await asyncio.sleep(2)
                else:
                    raise Exception(str(e))
        print("listen stop!")

    async def deal_xtx(self, dstool: DstTool, inter: Optional[ConnectorUnix] = None):
        """
        inter[: AsyncConnector] get key information from the relay chain in ToR mode
        1. listen xtx from queue_xtx:Queue
        2. get proof of xtx from src
        3. build tx for dst
        4. send tx to dst
        """

        L1tx_sent = {}

        tor_cs_height_on_inter = {}
        async def wait_header(height: int, synced_height: int, synced_inter_height: int) -> int:
            if self.mode in [Mode.MODENOR, Mode.MODEAOR]:
                while synced_height < height:
                    synced_height = await dstool.connector.query_max_xbn(self.src.pid)
                    if synced_height >= height:
                        break
                    await asyncio.sleep(0.5)
                return synced_height, synced_inter_height
            elif self.mode == Mode.MODETOR and self.rlytp == ToRRelayerType.PAP:
                # since the previous check_xtx has been checked, that is, the transaction should be forwarded by the current relayer, and the current relayer is a PAP relayer
                # check if the source chain block header is confirmed on the relay chain
                while synced_inter_height < height:
                    synced_inter_height = await inter.query_max_xbn(self.src.pid)
                    if synced_inter_height >= height:
                        # print(
                        #     f"inter synced_inter_height({synced_inter_height}) >= height({height})"
                        # )
                        break
                    # print(
                    #     f"wait inter synced_inter_height({synced_inter_height}) to tx.height({height})"
                    # )
                    await asyncio.sleep(0.5)
                if not tor_cs_height_on_inter.get(height, None):
                    tor_cs_height_on_inter[height] = await inter.query_header_cs_height(self.src.pid, height)
                inter_height = tor_cs_height_on_inter[height]
                # Check if the relay chain block header (including the source chain block header) is confirmed on the destination chain
                while synced_height < inter_height:
                    synced_height = await dstool.connector.query_max_xbn(inter.pid)
                    if synced_height >= inter_height:
                        # print(
                        #     f"dst synced_height({synced_height}) >= inter_height({inter_height})"
                        # )
                        break
                    # print(
                    #     f"wait dst synced_height({synced_height}) to tx.inter_height({inter_height})"
                    # )
                    await asyncio.sleep(1)
                if not L1tx_sent.get(height, False):
                    # for the src height is height block, if the current gateway has not submitted an L1 transaction, submit an L1 transaction, otherwise do not submit;
                    # in the case of multiple gateways, this method will repeat the submission;
                    # first submit the L1 level verification transaction
                    L1tx_sent[height] = True
                    memoL1 = json.dumps(
                        {
                            "type": TranMemo.CTXDSTL1,
                            "dst": dstool.connector.pid,
                            "ts": {"relayer/L1send": time.time()},
                        }
                    )
                    dataL1 = json.dumps(
                        {
                            "func": "validate_state",
                            "arguments": [
                                inter.pid,
                                inter.paratype,
                                inter_height,
                                state,
                            ],
                        }
                    )
                    txL1 = dstool.connector.build_tx(data=dataL1, memo=memoL1)
                    txhash = await dstool.connector.send_tx(txL1)
                    # print(f"wait L1 tx: {txhash}")
                    # dst.wait_tx(txhash)
                    # print(f"obtained L1 tx: {txhash}")
                return synced_height, synced_inter_height
            else:
                raise Exception("invalid relayer mode")

        # listening
        task_stop = asyncio.create_task(
            wait_stop(self.xtx_event_stop, dstool.queue_xtx)
        )
        await asyncio.sleep(0.5)

        synced_height = 0
        synced_inter_height = 0
        while True:
            try:
                xtx: Transaction = await dstool.queue_xtx.get()
                if xtx is None:
                    print("receive xtx:None STOP signal")
                    break

                # get the proof of the transaction
                proof = await self.src.query_xtx_proof(xtx)
                state = json.dumps(
                    {
                        "tx": xtx.as_json(),
                        "proof": proof,
                    }
                )
                # build the transaction, if the transaction is the UV protocol of ToR, then the source chain uses the Simple type
                # Simple type means that the L2 state proof of the UV protocol transaction is simple
                srctype = self.src.paratype
                if self.mode == Mode.MODETOR:
                    if self.src.paratype != dstool.connector.paratype:
                        srctype = "Simple"
                data = json.dumps(
                    {
                        "func": "validate_state",
                        "arguments": [
                            self.src.pid,
                            srctype,
                            xtx.height,
                            state,
                        ],
                    }
                )
                tx = dstool.connector.build_tx(data=data, memo=xtx.memo)

                # wait for the block header of the cross-chain transaction to be confirmed on the other chain
                mark_tx(tx, time_key="ready")
                height = xtx.height
                synced_height, synced_inter_height = await wait_header(height, synced_height, synced_inter_height)

                # send the cross-chain transaction to the other chain
                mark_tx(tx, time_key="send")
                await dstool.connector.send_tx(tx)
                await asyncio.sleep(0.01)
            except Exception as e:
                print(f"deal_xtx error: {traceback.format_exc()}")  
                break
            finally:
                pass
        if not task_stop.done():
            task_stop.cancel()
            await asyncio.sleep(0.1)

    async def deal_header(self, dstool: DstTool, inter: ConnectorUnix = None):
        """
        1. listern header from queue_header:Queue
        2. build tx for dst
        3. send tx to dst
        """

        async def check_tor_uv(height: int):
            """
            first judge whether the current gateway is a PAR gateway
            first query the source chain whether there is a UV protocol transaction
            if there is, then send a transaction to the relay chain
            """
            if not (self.mode == Mode.MODETOR and self.rlytp == ToRRelayerType.PAR):
                return

            # PAR and dst is interchain
            if not dstool.connector.isinter:
                return

            exists = await self.src.query_uv_exists(int(height))
            if not exists:
                return

            # send the "UV state root" verification transaction to the relay chain
            dataUV = json.dumps(
                {
                    "func": "validate_state",
                    "arguments": [
                        self.src.pid,
                        self.src.paratype,
                        header["height"],
                        "UV state root",
                    ],
                }
            )
            txUV = dstool.connector.build_tx(
                data=data,
                memo=json.dumps(
                    {
                        "type": TranMemo.CTXINTERUV,
                        "src": self.src.pid,
                        "height": header["height"],
                        "ts": {"UV/send": time.time()},
                    }
                ),
            )
            await dstool.connector.send_tx(txUV)

        # listening
        task_stop = asyncio.create_task(
            wait_stop(self.header_event_stop, dstool.queue_header)
        )
        await asyncio.sleep(0.5)

        while True:
            try:
                header = await dstool.queue_header.get()
                if header is None:
                    print("receive header:None STOP signal")
                    break
                data = json.dumps(
                    {
                        "func": "header_sync",
                        "arguments": [
                            self.src.pid,
                            self.src.paratype,
                            header["height"],
                            header,
                        ],
                    }
                )
                tx = dstool.connector.build_tx(
                    data=data,
                    memo=json.dumps(
                        {
                            "type": TranMemo.CTXHDR,
                            "src": self.src.pid,
                            "height": header["height"],
                            "ts": {"header/send": time.time()},
                        }
                    ),
                )
                await dstool.connector.send_tx(tx)
                await asyncio.sleep(0.01)

                # MARK: whether to apply the UV mode
                # check_tor_uv(int(header["height"]))

                # time.sleep(0.1)  # TODO get it from config
            except Exception as e:
                print(f"deal_header error: {traceback.format_exc()}") 
                break

        if not task_stop.done():
            task_stop.cancel()
            await asyncio.sleep(0.1)

    def stop(
        self,
    ):
        self.stop_listen_block()
        self.stop_deal_header()
        self.stop_deal_xtx()
        self.dsts.close()
        self.src.close()

    def stop_listen_block(
        self,
    ):
        self.listen_event_stop.set()

    def stop_deal_header(
        self,
    ):
        self.header_event_stop.set()
        # self.queue_header.put(None)

    def stop_deal_xtx(
        self,
    ):
        self.xtx_event_stop.set()
        # self.queue_xtx.put(None)

    async def start_one_way(self):
        await asyncio.gather(
            self.listen_block(),
        )

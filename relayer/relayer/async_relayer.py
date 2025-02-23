from __future__ import annotations
import time
import asyncio
import json
import multiprocessing
import traceback
import queue
from typing import List, Tuple
from relayer.connector.async_connector import AsyncConnector
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
    """In ToR mode, the type of gateway"""

    PAR = 0  # the relayer between the relay chain and the parachain, only synchronize block headers
    PAP = 1  # the relayer between the parachains, only synchronize cross-chain transactions

    @staticmethod
    def is_relayertype(_type: int) -> bool:
        return _type in (ToRRelayerType.PAR, ToRRelayerType.PAP)


class AsyncRelayer(object):
    def __init__(
        self,
        src: AsyncConnector,
        dst: AsyncConnector,
        mode: str,
        inter: AsyncConnector = None,
        rlytp: ToRRelayerType = None,
    ) -> None:
        assert isinstance(src, AsyncConnector)
        assert isinstance(dst, AsyncConnector)
        self.src = src
        self.dst = dst

        assert Mode.is_mode(mode), f"invalid mode({mode})"
        self.mode = mode
        self.rlytp = rlytp
        self.inter = inter
        if mode == Mode.MODETOR:
            # pap: ToR mode, whether the relayer is between the relay chain and the parachain
            # par: ToR mode, whether the relayer is between the parachains
            # pap and par can only have 1 true
            # if pap is true, then inter: AsyncConnector cannot be empty
            assert ToRRelayerType.is_relayertype(self.rlytp)
            if self.rlytp == ToRRelayerType.PAP:
                # if the relayer is between the parachains, then inter must be assigned
                assert isinstance(self.inter, AsyncConnector)
            else:
                # if the relayer is between the relay chain and the parachain, then src and dst must have only 1 true
                assert self.src.isinter ^ self.dst.isinter
        else:
            # in AoR or NoR mode, rlytp cannot be set
            assert self.rlytp is None

        # starttime = time.time()
        self.queue_header = asyncio.Queue()
        # print(f"create queue cost: {time.time()-starttime}")
        # starttime = time.time()
        self.queue_xtx = asyncio.Queue()
        # print(f"create queue2 cost: {time.time()-starttime}")
        # starttime = time.time()
        self.listen_event_stop = asyncio.Event()
        self.header_event_stop = asyncio.Event()
        self.xtx_event_stop = asyncio.Event()
        # print(f"create Event cost: {time.time()-starttime}")

    def is_xtx(self, tx: Transaction) -> bool:
        """
        whether the type of tx.memo is SRC-CTX or INTER-CTX
        """
        memo = json.loads(tx.memo)
        return memo.get("type") in [TranMemo.CTXSRC, TranMemo.CTXINTER]

    async def filter_header(self, header: dict):
        """filter header which should be transmitted to dst chain

        :param header: block header
        :type header: dict
        """
        if self.mode in (Mode.MODEAOR, Mode.MODENOR):
            # AoR or NoR mode
            await self.queue_header.put(header)
        elif self.mode == Mode.MODETOR and self.rlytp == ToRRelayerType.PAR:
            # ToR mode, and the relayer is par type
            await self.queue_header.put(header)

    async def filter_txs(self, txs: List[Transaction]) -> int:
        """filter crosschain txs from all transactions in a block

        :param txs: transactions in a block
        :type txs: List[Transaction]
        """
        if self.mode == Mode.MODETOR and self.rlytp == ToRRelayerType.PAR:
            # ToR mode, and the relayer is par type, no need to forward cross-chain transactions
            return
        cnt = 0
        for tx in txs:
            if self.is_xtx(tx) and tx.status == TxStatus.SUCCESS:
                mark_tx(tx, time_key="listened")
                await self.queue_xtx.put(tx)
                cnt += 1
        return cnt

    async def listen_block(self, src: AsyncConnector, dst: AsyncConnector):
        """
        listen latest block every 2 seconds and:
        1. put header to queue_header:Queue
        2. put successful xtx to queue_xtx:Queue
        """
        maxbn = await dst.query_max_xbn(src.pid)
        if maxbn == 0: 
            cur_height = await src.query_block_number()
            maxbn = cur_height - 1
        nextbn = maxbn + 1
        while not self.listen_event_stop.is_set():
            try:
                latestblock = await src.query_block(bn=nextbn)
                header = latestblock.header()
                await self.filter_header(header)
                xtx_cnt = await self.filter_txs(latestblock.txs)
                print(f"listen_block({nextbn}) ok, find xtx cnt:{xtx_cnt}")
                nextbn += 1
            except Exception as e:
                print(f"listen_block({nextbn}) warning: {str(e)}")
                await asyncio.sleep(2)  # TODO read sleep time from config
            finally:
                await asyncio.sleep(1)
                pass
        print("listen stop!")

    async def deal_xtx(
        self, src: AsyncConnector, dst: AsyncConnector, inter: AsyncConnector = None
    ):
        """
        1. listen xtx from queue_xtx:Queue
        2. get proof of xtx from src
        3. build tx for dst
        4. send tx to dst
        """

        # {height: bool}, for the src height is height block, whether the L1 transaction has been submitted;
        # since deal_xtx only processes the unilateral process between a pair of parachains, so L1tx_sent will not be covered by other chains, so only height as the key is enough
        # only works in ToR mode
        L1tx_sent = {}

        def check_xtx(xtx: Transaction) -> Tuple[bool, str]:
            """check if the destination chain of xtx is the destination chain of the current relayer to determine if forwarding is needed

            :param xtx: cross-chain transaction
            :type xtx: Transaction
            :return: whether forwarding is needed
            :rtype: bool
            """
            memo: dict = json.loads(xtx.memo)
            xtxtype = memo["type"]
            # mode = memo["mode"]
            if self.mode == Mode.MODENOR:
                if xtxtype == TranMemo.CTXSRC:
                    if int(memo.get("dst", -1)) == dst.pid:
                        memo.update({"type": TranMemo.CTXDST, "src": src.pid})
                        return True, json.dumps(memo)
            elif self.mode == Mode.MODEAOR:
                if xtxtype == TranMemo.CTXSRC:
                    if dst.isinter:
                        memo.update({"type": TranMemo.CTXINTER, "src": src.pid})
                        return True, json.dumps(memo)
                elif xtxtype == TranMemo.CTXINTER:
                    if int(memo.get("dst", -1)) == dst.pid:
                        memo.update({"type": TranMemo.CTXDST, "src": src.pid})
                        return True, json.dumps(memo)
            elif self.mode == Mode.MODETOR and self.rlytp == ToRRelayerType.PAP:
                # in ToR mode, only pap type relayer needs to forward transactions
                if xtxtype == TranMemo.CTXSRC:
                    if int(memo.get("dst", -1)) == dst.pid:
                        memo.update({"type": TranMemo.CTXDST, "src": src.pid})
                        return True, json.dumps(memo)
            else:
                print(f"warning: watched illegal cross mode = {memo}")
            return False, ""

        async def wait_header(height: int, synced_height: int) -> int:
            if self.mode in [Mode.MODENOR, Mode.MODEAOR]:
                while synced_height < height:
                    synced_height = await dst.query_max_xbn(src.pid)
                    if synced_height >= height:
                        break
                    await asyncio.sleep(0.5)
                return synced_height
            elif self.mode == Mode.MODETOR and self.rlytp == ToRRelayerType.PAP:
                # since check_xtx has been checked, the transaction should be forwarded by the current relayer, and the current relayer is a PAP relayer
                # check if the source chain block header is confirmed on the relay chain
                synced_inter_height = 0
                while synced_inter_height < height:
                    synced_inter_height = await inter.query_max_xbn(src.pid)
                    if synced_inter_height >= height:
                        print(
                            f"inter synced_inter_height({synced_inter_height}) >= height({height})"
                        )
                        break
                    print(
                        f"wait inter synced_inter_height({synced_inter_height}) to tx.height({height})"
                    )
                    await asyncio.sleep(0.5)
                inter_height = await inter.query_header_cs_height(src.pid, height)
                # check if the relay chain block header (including the source chain block header) is confirmed on the destination chain
                while synced_height < inter_height:
                    synced_height = await dst.query_max_xbn(inter.pid)
                    if synced_height >= inter_height:
                        print(
                            f"dst synced_height({synced_height}) >= inter_height({inter_height})"
                        )
                        break
                    print(
                        f"wait dst synced_height({synced_height}) to tx.inter_height({inter_height})"
                    )
                    await asyncio.sleep(1)
                if not L1tx_sent.get(height, False):
                    # for the src height is height block, if the current relayer has not submitted the L1 transaction, then submit the L1 transaction, otherwise not submit;
                    # in the case of multiple relayers, this method will submit the L1 transaction repeatedly;
                    # first submit the L1 level verification transaction
                    L1tx_sent[height] = True
                    memoL1 = json.dumps(
                        {
                            "type": TranMemo.CTXDSTL1,
                            "dst": dst.pid,
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
                    txL1 = dst.build_tx(data=dataL1, memo=memoL1)
                    txhash = await dst.send_tx(txL1)
                    # print(f"wait L1 tx: {txhash}")
                    # dst.wait_tx(txhash)
                    # print(f"obtained L1 tx: {txhash}")
                return synced_height
            else:
                raise Exception("invalid relayer mode")

        # listening
        task_stop = asyncio.create_task(wait_stop(self.xtx_event_stop, self.queue_xtx))
        await asyncio.sleep(0.5)

        synced_height = 0
        while True:
            try:
                xtx: Transaction = await self.queue_xtx.get()
                if xtx is None:
                    print("receive xtx:None STOP signal")
                    break
                # check if the transaction should be forwarded by the current relayer
                should, memo = check_xtx(xtx)
                if not should:
                    continue
                # mark_tx(xtx, time_key="deal")

                # get the proof of the transaction
                proof = await src.query_xtx_proof(xtx)
                state = json.dumps(
                    {
                        "tx": xtx.as_json(),
                        "proof": proof,
                    }
                )
                # build the transaction, if the transaction is ToR's UV protocol, then the source chain uses the Simple type
                # Simple type means that the L2 state proof of the UV protocol transaction is simple
                srctype = src.paratype
                if self.mode == Mode.MODETOR:
                    if src.paratype != dst.paratype:
                        srctype = "Simple"
                data = json.dumps(
                    {
                        "func": "validate_state",
                        "arguments": [
                            src.pid,
                            srctype,
                            xtx.height,
                            state,
                        ],
                    }
                )
                tx = dst.build_tx(data=data, memo=memo)

                # wait for the block header of the cross-chain transaction to be confirmed on the destination chain
                mark_tx(tx, time_key="ready")
                height = xtx.height
                synced_height = await wait_header(height, synced_height)

                # send the cross-chain transaction to the other side
                mark_tx(tx, time_key="send")
                await dst.send_tx(tx)
                await asyncio.sleep(0.01)
            except Exception as e:
                print(f"deal_xtx error: {traceback.format_exc()}")  
                break
            finally:
                pass
        if not task_stop.done():
            task_stop.cancel()
            await asyncio.sleep(0.1)

    async def deal_header(
        self, src: AsyncConnector, dst: AsyncConnector, inter: AsyncConnector = None
    ):
        """
        1. listern header from queue_header:Queue
        2. build tx for dst
        3. send tx to dst
        """

        async def check_tor_uv(height: int):
            """
            first check if the current relayer is a PAR relayer
            then query the source chain whether there is a UV protocol transaction
            if there is, then send a transaction to the relay chain
            """
            if not (self.mode == Mode.MODETOR and self.rlytp == ToRRelayerType.PAR):
                return

            # PAR and dst is interchain
            if not dst.isinter:
                return

            exists = await src.query_uv_exists(int(height))
            if not exists:
                return

            # send the "UV state root" verification transaction to the relay chain
            dataUV = json.dumps(
                {
                    "func": "validate_state",
                    "arguments": [
                        src.pid,
                        src.paratype,
                        header["height"],
                        "UV state root",
                    ],
                }
            )
            txUV = dst.build_tx(
                data=data,
                memo=json.dumps(
                    {
                        "type": TranMemo.CTXINTERUV,
                        "src": src.pid,
                        "height": header["height"],
                        "ts": {"UV/send": time.time()},
                    }
                ),
            )
            await dst.send_tx(txUV)

        # listening
        task_stop = asyncio.create_task(
            wait_stop(self.header_event_stop, self.queue_header)
        )
        await asyncio.sleep(0.5)

        while True:
            try:
                header = await self.queue_header.get()
                if header is None:
                    print("receive header:None STOP signal")
                    break
                data = json.dumps(
                    {
                        "func": "header_sync",
                        "arguments": [
                            src.pid,
                            src.paratype,
                            header["height"],
                            header,
                        ],
                    }
                )
                tx = dst.build_tx(
                    data=data,
                    memo=json.dumps(
                        {
                            "type": TranMemo.CTXHDR,
                            "src": src.pid,
                            "height": header["height"],
                            "ts": {"header/send": time.time()},
                        }
                    ),
                )
                await dst.send_tx(tx)
                await asyncio.sleep(0.01)

                # MARK: whether to apply UV mode
                # check_tor_uv(int(header["height"]))
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
            self.listen_block(self.src, self.dst),
            self.deal_header(self.src, self.dst, self.inter),
            self.deal_xtx(self.src, self.dst, self.inter),
        )

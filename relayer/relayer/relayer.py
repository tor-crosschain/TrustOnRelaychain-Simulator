from __future__ import annotations
import time
import json
import multiprocessing
import traceback
import queue
from typing import List, Tuple
from relayer.connector.connector import Connector
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


class Relayer(object):
    def __init__(
        self,
        src: Connector,
        dst: Connector,
        mode: str,
        inter: Connector = None,
        rlytp: ToRRelayerType = None,
    ) -> None:
        assert isinstance(src, Connector)
        assert isinstance(dst, Connector)
        self.src = src
        self.dst = dst

        assert Mode.is_mode(mode), f"invalid mode({mode})"
        self.mode = mode
        self.rlytp = rlytp
        self.inter = inter
        if mode == Mode.MODETOR:
            # pap: In ToR, whether it is a gateway between the relay chain and the parachain
            # par: In ToR, whether it is a gateway between parachains
            # Only one of pap and par can be true
            # If pap is true, then inter: Connector cannot be None
            assert ToRRelayerType.is_relayertype(self.rlytp)
            if self.rlytp == ToRRelayerType.PAP:
                # If it is a parachain gateway, then inter must be assigned
                assert isinstance(self.inter, Connector)
            else:
                # If it is a relay chain and parachain gateway, then src and dst must have only 1 true
                assert self.src.isinter ^ self.dst.isinter
        else:
            # In AoR or NoR mode, rlytp cannot be set
            assert self.rlytp is None

        # starttime = time.time()
        self.queue_header = multiprocessing.Manager().Queue()
        # print(f"create queue cost: {time.time()-starttime}")
        # starttime = time.time()
        self.queue_xtx = multiprocessing.Manager().Queue()
        # print(f"create queue2 cost: {time.time()-starttime}")
        # starttime = time.time()
        self.listen_event_stop = multiprocessing.Event()
        # print(f"create Event cost: {time.time()-starttime}")
        self.stopped_listen_block = False

    def is_xtx(self, tx: Transaction) -> bool:
        """
        whether the type of tx.memo is SRC-CTX
        """
        memo = json.loads(tx.memo)
        return memo.get("type") in [TranMemo.CTXSRC, TranMemo.CTXINTER]

    def filter_header(self, header: dict):
        """filter header which should be transmitted to dst chain

        :param header: block header
        :type header: dict
        """
        if self.mode in (Mode.MODEAOR, Mode.MODENOR):
            # It is AoR or NoR mode
            self.queue_header.put(header)
        elif self.mode == Mode.MODETOR and self.rlytp == ToRRelayerType.PAR:
            # It is ToR mode, and it is a par type gateway
            self.queue_header.put(header)

    def filter_txs(self, txs: List[Transaction]) -> int:
        """filter crosschain txs from all transactions in a block

        :param txs: transactions in a block
        :type txs: List[Transaction]
        """
        if self.mode == Mode.MODETOR and self.rlytp == ToRRelayerType.PAR:
            # It is ToR mode, and it is a par type gateway, no need to forward cross-chain transactions
            return
        cnt = 0
        for tx in txs:
            if self.is_xtx(tx) and tx.status == TxStatus.SUCCESS:
                mark_tx(tx, time_key="listened")
                self.queue_xtx.put(tx)
                cnt += 1
        return cnt

    def listen_block(self, src: Connector, dst: Connector):
        """
        listen latest block every 2 seconds and:
        1. put header to queue_header:Queue
        2. put successful xtx to queue_xtx:Queue
        """
        maxbn = dst.query_max_xbn(src.pid)
        if maxbn == 0:  # If dst has not received the block header of src, then only synchronize from the latest block header of src
            cur_height = src.query_block_number()
            maxbn = cur_height - 1
        nextbn = maxbn + 1
        while not self.listen_event_stop.is_set():
            try:
                latestblock = src.query_block(bn=nextbn)
                header = latestblock.header()
                self.filter_header(header)
                xtx_cnt = self.filter_txs(latestblock.txs)
                print(f"listen_block({nextbn}) ok, find xtx cnt:{xtx_cnt}")
                nextbn += 1
            except Exception as e:
                print(f"listen_block({nextbn}) warning: {str(e)}")
                time.sleep(2)  # TODO read sleep time from config
            finally:
                time.sleep(0.01)
                pass
        print("listen stop!")

    def deal_xtx(self, src: Connector, dst: Connector, inter: Connector = None):
        """
        1. listen xtx from queue_xtx:Queue
        2. get proof of xtx from src
        3. build tx for dst
        4. send tx to dst
        """

        L1tx_sent = {}

        def check_xtx(xtx: Transaction) -> Tuple[bool, str]:
            """Check if the destination chain of xtx is the destination chain of the current relayer to determine if forwarding is needed

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
                # In ToR mode, only pap type relayer needs to forward transactions
                if xtxtype == TranMemo.CTXSRC:
                    if int(memo.get("dst", -1)) == dst.pid:
                        memo.update({"type": TranMemo.CTXDST, "src": src.pid})
                        return True, json.dumps(memo)
            else:
                print(f"warning: watched illegal cross mode = {memo}")
            return False, ""

        def wait_header(height: int, synced_height: int) -> int:
            if self.mode in [Mode.MODENOR, Mode.MODEAOR]:
                while synced_height < height:
                    synced_height = dst.query_max_xbn(src.pid)
                    if synced_height >= height:
                        break
                    time.sleep(0.2)
                return synced_height
            elif self.mode == Mode.MODETOR and self.rlytp == ToRRelayerType.PAP:
                # Since check_xtx has been checked, the transaction should be forwarded by the current relayer, and the current relayer is a PAP relayer
                # Check if the source chain block header is confirmed on the relay chain
                synced_inter_height = 0
                while synced_inter_height < height:
                    synced_inter_height = inter.query_max_xbn(src.pid)
                    if synced_inter_height >= height:
                        print(
                            f"inter synced_inter_height({synced_inter_height}) >= height({height})"
                        )
                        break
                    print(
                        f"wait inter synced_inter_height({synced_inter_height}) to tx.height({height})"
                    )
                    time.sleep(0.2)
                inter_height = inter.query_header_cs_height(src.pid, height)
                # Check if the relay chain block header (including the source chain block header) is confirmed on the destination chain
                while synced_height < inter_height:
                    synced_height = dst.query_max_xbn(inter.pid)
                    if synced_height >= inter_height:
                        print(
                            f"dst synced_height({synced_height}) >= inter_height({inter_height})"
                        )
                        break
                    print(
                        f"wait dst synced_height({synced_height}) to tx.inter_height({inter_height})"
                    )
                    time.sleep(1)
                if not L1tx_sent.get(height, False):
                    # For the src height is height block, if the current relayer has not submitted the L1 transaction, then submit the L1 transaction, otherwise not submit;
                    # In the case of multiple relayers, this method will submit the L1 transaction repeatedly;
                    # First submit the L1 level verification transaction
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
                    txhash = dst.send_tx(txL1)
                    # print(f"wait L1 tx: {txhash}")
                    # dst.wait_tx(txhash)
                    # print(f"obtained L1 tx: {txhash}")
                return synced_height
            else:
                raise Exception("invalid relayer mode")

        synced_height = 0
        while True:
            try:
                xtx: Transaction = self.queue_xtx.get(block=True)
                if xtx is None:
                    print("receive xtx:None STOP signal")
                    break
                # Check if the transaction should be forwarded by the current relayer
                should, memo = check_xtx(xtx)
                if not should:
                    continue
                # mark_tx(xtx, time_key="deal")

                # Get the proof of the transaction
                proof = src.query_xtx_proof(xtx)
                state = json.dumps(
                    {
                        "tx": xtx.as_json(),
                        "proof": proof,
                    }
                )
                # Build the transaction, if the transaction is ToR's UV protocol, then the source chain uses the Simple type
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

                # Wait for the block header of the cross-chain transaction to be confirmed on the other side
                mark_tx(tx, time_key="ready")
                height = xtx.height
                synced_height = wait_header(height, synced_height)

                # Send the cross-chain transaction to the other side
                mark_tx(tx, time_key="send")
                dst.send_tx(tx)
            except Exception as e:
                print(f"deal_xtx error: {traceback.format_exc()}")  
                return
            finally:
                pass

    def deal_header(self, src: Connector, dst: Connector, inter: Connector = None):
        """
        1. listern header from queue_header:Queue
        2. build tx for dst
        3. send tx to dst
        """

        def check_tor_uv(height: int):
            """
            First check if the current relayer is a PAR relayer
            Then query the source chain whether there is a UV protocol transaction
            If there is, then send a transaction to the relay chain
            """
            if not (self.mode == Mode.MODETOR and self.rlytp == ToRRelayerType.PAR):
                return

            # PAR and dst is interchain
            if not dst.isinter:
                return

            exists = src.query_uv_exists(int(height))
            if not exists:
                return

            # Send the "UV state root" verification transaction to the relay chain
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
            dst.send_tx(txUV)

        while True:
            try:
                header = self.queue_header.get(block=True)
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
                dst.send_tx(tx)

                # MARK: whether to apply UV mode
                # check_tor_uv(int(header["height"]))
            except Exception as e:
                print(f"deal_header error: {traceback.format_exc()}") 
                return

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
        self.queue_header.put(None)

    def stop_deal_xtx(
        self,
    ):
        self.queue_xtx.put(None)

    def start_one_way(self):
        proc0 = multiprocessing.Process(
            target=self.listen_block, args=(self.src, self.dst)
        )
        proc1 = multiprocessing.Process(
            target=self.deal_xtx, args=(self.src, self.dst, self.inter)
        )
        proc2 = multiprocessing.Process(
            target=self.deal_header, args=(self.src, self.dst, self.inter)
        )

        proc0.start()
        proc1.start()
        proc2.start()

        proc0.join()
        proc1.join()
        proc2.join()

        print("start_one_way STOP!")

    @staticmethod
    def start_two_way(s2d: Relayer, d2s: Relayer):
        proc1 = multiprocessing.Process(target=s2d.start_one_way)
        proc2 = multiprocessing.Process(target=d2s.start_one_way)
        proc1.start()
        proc2.start()

        proc1.join()
        proc2.join()

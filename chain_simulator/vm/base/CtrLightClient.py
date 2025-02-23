"""
Implements light client:
- Block header synchronization
- State verification
"""
import json
import time
import asyncio
from chain_simulator.vm.icode import CodeMeta


class CtrLightClient(CodeMeta):
    CROSSTYPES = ["NoR", "AoR", "ToR"]

    def __init__(self) -> None:
        super().__init__()

    def init(self, *args, **kwargs) -> None:
        # Set execution time for light clients with different connections in ms
        # A-B-s: A verify s from B
        self.store.set("Ethereum-Tendermint-header", "13.2")  # 6 validators - 13.2ms
        self.store.set("Ethereum-Tendermint-state", "11.07")  # 11.07 ms
        self.store.set("Ethereum-Ethereum-header", "25.5")  # 25.5 ms
        self.store.set("Ethereum-Ethereum-state", "1")  # < 1 ms
        self.store.set("Tendermint-Ethereum-header", "2.8")  # 2.8 ms
        self.store.set("Tendermint-Ethereum-state", "1")  # < 1 ms
        self.store.set("Tendermint-Tendermint-header", "1")  # 1 ms
        self.store.set("Tendermint-Tendermint-state", "1.5")  # 1.7 ms

        # Heterogeneous systems uses UV protocol for verification, UV protocol uses simple (relay chain) protocol for state verification
        # Since the proof content is very short (only builds Merkle tree with cross-chain transactions in current block)
        self.store.set("Tendermint-Simple-state", "1")
        self.store.set("Ethereum-Simple-state", "1")

    async def exec(self, rawdata: str) -> str:
        """_summary_

        :param rawdata: _description_
        :type rawdata: str
        :return: _description_
        :rtype: str
        """
        data = json.loads(rawdata)
        func = f"_{data['func']}"
        assert func in [
            "_header_sync",
            "_validate_state",
            "_set_paraid",
            "_set_paratype",
            "_app_init",
        ], f"func({func}) is illegal"
        arguments = data["arguments"]
        assert isinstance(arguments, list), "arguments should be list"
        return await getattr(self, func)(*arguments)

    async def _app_init(self, dst_chainid: int, dst_chaintype: str, appdata: str):
        """
        Called by user
        """
        assert isinstance(
            dst_chainid, int
        ), f"dst_chainid({type(dst_chainid)}) must be int"
        assert isinstance(
            dst_chaintype, str
        ), f"dst_chaintype({type(dst_chaintype)}) must be str"
        assert isinstance(appdata, str), f"appdata({type(appdata)}) must be str"
        chaintype = self.store.get("paratype")
        assert chaintype is not None, "find no paratype"
        if chaintype != dst_chaintype:
            """
            Preparation for ToR's UV protocol
            Although AoR and NoR will also execute, the gateway won't fetch it
            Only ToR's PAR gateway will fetch this data
            Store with height as unique identifier
            """
            uv_key = f"uv_exists_{self.ctx.block.height}"
            self.store.set(uv_key, "1")

    async def _set_paraid(self, paraid: int):
        self.store.set("paraid", str(paraid))

    async def _set_paratype(self, paratype: str):
        self.store.set("paratype", str(paratype))

    async def _set_crosstype(self, crosstype: str):
        assert crosstype in self.CROSSTYPES, f"crosstype({crosstype}) is invalid"
        self.store.set("crosstype", str(crosstype))

    def __header_key(self, paraid: int, height: int) -> str:
        """When height = 0, the value corresponding to this key is the count"""
        return f"header-{paraid}-{height}"

    def __state_key(self, paraid: int, height: int, idx: int) -> str:
        """When idx = 0, the value corresponding to this key is the count"""
        return f"state-{paraid}-{height}-{idx}"

    def __exec_sleep(self, stype: str, paratype: str):
        assert stype in ["header", "state"], f"stype({stype}) is invalid"
        crosstype = self.store.get("crosstype", None)
        assert crosstype is not None, "crosstype has not been set!"
        chaintype = self.store.get("paratype")
        assert chaintype is not None, "find no paratype"

        exec_time = 0
        if crosstype in ["AoR", "NoR"]:
            exec_time = float(
                self.store.get("{}-{}-{}".format(chaintype, paratype, stype))
            )
        elif crosstype == "ToR":

            exec_time = float(
                self.store.get("{}-{}-{}".format(chaintype, paratype, stype))
            )

        time.sleep(exec_time / 1000.0)  # 毫秒

    async def _header_sync(
        self, paraid: int, paratype: str, height: int, header: str
    ) -> str:
        """Block header synchronization
        Simply store it for gateway to check if the block header of the transaction has been submitted before forwarding

        :param paraid: Parallel chain identifier
        :type paraid: int
        :param height: Block height to sync
        :type height: int
        :param header: Block header to sync
        :type header: str(json)
        :return: Sync success('1') or failure('0')
        :rtype: str
        """
        header_cnt_key = self.__header_key(paraid, 0)
        cnt = self.store.get(header_cnt_key)
        if cnt is None:
            cnt = "0"
        cnt = max(int(cnt), height)
        header_key = self.__header_key(paraid, height)
        data = json.dumps(
            {
                "header": header,
                "cs_height": self.ctx.block.height,
            }
        )
        self.store.set(header_key, data)
        self.store.set(header_cnt_key, str(cnt))

        chaintype = self.store.get("paratype")
        assert chaintype is not None, "find no paratype"
        exec_time = float(self.store.get("{}-{}-header".format(chaintype, paratype)))
        await asyncio.sleep(exec_time / 1000.0)  # ms
        return header_key

    async def _validate_state(
        self, paraid: int, paratype: str, height: int, state: str
    ) -> str:
        """State verification

        :param paraid: Parallel chain identifier
        :type paraid: int
        :param height: Block height
        :type height: int
        :param state: State to verify
        :type state: str
        :return: Verification success(state_key) or failure('0')
        :rtype: str
        """
        header_key = self.__header_key(paraid, height)
        header = self.store.get(header_key)
        assert header is not None, f"cannot find header: {header_key}"
        state_cnt_key = self.__state_key(paraid, height, 0)
        cnt = self.store.get(state_cnt_key)
        if not cnt:
            cnt = "0"
        cnt = int(cnt) + 1
        state_key = self.__state_key(paraid, height, cnt)
        self.store.set(state_key, state)
        self.store.set(state_cnt_key, str(cnt))

        # Wait for a fixed time according to the connection type
        chaintype = self.store.get("paratype")
        assert chaintype is not None, "find no paratype"
        exec_time = float(self.store.get("{}-{}-state".format(chaintype, paratype)))
        await asyncio.sleep(exec_time / 1000.0)  # ms
        return state_key

    def query(self, rawdata: str) -> str:
        data = json.loads(rawdata)
        arguments = data.get("arguments", [])
        assert isinstance(arguments, list), "arguments should be list"
        if not data.get("func", None):
            rs = []
            for arg in arguments:
                r = self.store.get(arg)
                if r is None:
                    r = ""
                rs.append(r)
            return rs
        func = f"_{data['func']}"
        return getattr(self, func)(*arguments)

    def _query_paraid(self) -> int:
        paraid = self.store.get("paraid")
        assert paraid is not None, "cannot find paraid"
        return int(paraid)

    def _query_paratype(self) -> str:
        paratype = self.store.get("paratype")
        assert paratype is not None, "cannot find paratype"
        return paratype

    def _query_header(self, paraid: int, height: int) -> str:
        header_key = self.__header_key(paraid, height)
        header = self.store.get(header_key)
        assert header is not None, f"cannot find header: {header_key}"
        return header

    def _query_header_maxn(self, paraid: int) -> str:
        header_cnt_key = self.__header_key(paraid, 0)
        cnt = self.store.get(header_cnt_key)
        if cnt is None:
            return "0"
        return cnt

    def _query_state(self, paraid: int, height: int, idx: int) -> str:
        state_key = self.__state_key(paraid, height, idx)
        state = self.store.get(state_key)
        assert state is not None, f"cannot find state: {state_key}"
        return state

    def _query_uv_exists(self, height: int) -> str:
        assert isinstance(height, int), f"height({type(height)}) must be int"
        uv_key = f"uv_exists_{height}"
        exists = self.store.get(uv_key)
        if exists is None:
            return "0"
        return "1"

"""
Implements basic read and write operations for key-value database
"""
import json
from chain_simulator.vm.icode import CodeMeta


class CtrBase(CodeMeta):
    def __init__(self) -> None:
        super().__init__()

    def init(self, *args, **kwargs) -> None:
        pass

    async def exec(self, rawdata: str) -> str:
        data = json.loads(rawdata)
        arguments = data["arguments"]
        assert isinstance(arguments, list), "arguments should be list"
        assert len(arguments) % 2 == 0, "arguments length must be even"
        for i in range(0, len(arguments), 2):
            key = str(arguments[i])
            value = str(arguments[i + 1])
            self.store.set(key, value)
        return ""

    def query(self, rawdata: str) -> str:
        data = json.loads(rawdata)
        arguments = data["arguments"]
        assert isinstance(arguments, list), "arguments should be list"
        if not data.get("func", None):
            rs = []
            for arg in arguments:
                r = self.store.get(arg)
                if r is None:
                    r = ""
                rs.append(r)
            return rs
        func = f"__{data['func']}"
        return getattr(self, func)(*arguments)

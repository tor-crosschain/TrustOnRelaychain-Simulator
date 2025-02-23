import json
from chain_simulator.vm.icode import CodeMeta


class CodeAdd(CodeMeta):
    def __init__(self) -> None:
        super().__init__()

    def init(self, *args, **kwargs) -> None:
        self.store.set("init", "hello")
        self.store.set("a", str(10))

    async def exec(self, rawdata: str) -> str:
        data = json.loads(rawdata)
        func = f"_{data['func']}"
        arguments = data["arguments"]
        assert isinstance(arguments, list), "arguments should be list"
        return await getattr(self, func)(*arguments)

    async def _add(self, *args) -> str:
        key, num = args
        num = int(num)
        old_num = self.store.get(key)
        if not old_num:
            old_num = 0
        old_num = int(old_num)
        old_num += num
        self.store.set(key, str(old_num))
        return str(old_num)

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

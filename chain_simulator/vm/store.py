class BaseStore(object):
    def __init__(self) -> None:
        self._store = {}

    def set(self, key: str, value: str) -> None:
        """Set content, both key and value are of type str"""
        assert isinstance(key, str), "instance of key is not str"
        assert isinstance(value, str), "instance of value is not str"
        self._store[key] = value

    def get(self, key):
        assert isinstance(key, str), "instance of key is not str"
        return self._store.get(key, None)

    def has_key(self, key):
        assert isinstance(key, str), "instance of key is not str"
        return key in self._store.keys()

    def len(self) -> int:
        return len(self._store)


class AccountStore(BaseStore):
    def __init__(self) -> None:
        super().__init__()
        self._code = ""

    def set_code(self, code: str) -> None:
        self._code = code

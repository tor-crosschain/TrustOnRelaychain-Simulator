import json
import abc
from chain_simulator.blockchain.context import Context
from chain_simulator.vm.store import BaseStore


class CodeMeta(object):
    def __init__(self) -> None:
        self.store: BaseStore = None
        self.ctx: Context = None

    @abc.abstractmethod
    def init(self, *args, **kwargs) -> None:
        raise NotImplementedError("unimplemented!")

    @abc.abstractmethod
    async def exec(self, rawdata: str) -> str:
        """Entry function for contract execution

        :param rawdata: Execution parameters: func, arguments
        :type rawdata: str
        :return: Returned data in JSON format
        :rtype: str
        """
        raise NotImplementedError("unimplemented!")

    @abc.abstractmethod
    def query(self, rawdata: str) -> str:
        """Query function for contract

        :param rawdata: Query parameters: func, arguments
        :type rawdata: str
        :return: Returned data in JSON format
        :rtype: str
        """
        raise NotImplementedError("unimplemented!")

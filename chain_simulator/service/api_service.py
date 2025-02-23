"""
This api is suitable for multi-thread and multi-process architecture, but not suitable for asynchronous architecture

The architecture refers to the relationship between api and bc
"""
import asyncio
import tornado.web
from typing import Dict
from chain_simulator.service.blockchain.transaction_handlers import (
    TransactionHandler,
)
from chain_simulator.service.blockchain.blockchain_handlers import (
    BlockchainHandler,
)

# from chain_simulator.mempool.mempool import SyncMemPool
from chain_simulator.blockchain.blockchain_p import BlockchainStates


class ApiService(object):
    def __init__(self, blockchain_states: BlockchainStates) -> None:
        self.bcstates = blockchain_states
        self.stop_event: asyncio.Event = None

    def make_app(self, args: Dict = None) -> tornado.web.Application:
        if args is None:
            args = {}
        args.update({"bcstates": self.bcstates})
        handlers = [
            TransactionHandler,
            BlockchainHandler,
        ]
        routes = []
        for handler in handlers:
            routes += [(route, handler, args) for route in handler.routers().keys()]
        return tornado.web.Application(routes)

    async def run_app(self, args: Dict = None):
        if args is None:
            args = {}
        app = self.make_app(args)
        port = args.get("port", 8888)
        server = app.listen(port=port)
        print(f"api service({port}) is listening...")
        self.stop_event = asyncio.Event()
        await self.stop_event.wait()
        server.stop()
        print(f"api service({port}) stopped!")

    def stop(self) -> None:
        assert self.stop_event is not None
        self.stop_event.set()

    def run(self, args: Dict) -> None:
        asyncio.run(self.run_app(args))

import multiprocessing
import types
from multiprocessing.managers import BaseManager, DictProxy, ListProxy, NamespaceProxy
from chain_simulator.types.transaction import TranMemo, TransactionIndexer
from chain_simulator.vm.store import BaseStore
from chain_simulator.types.block import Block, BlockStorage
from chain_simulator.mempool.mempool import SyncMemPool
from chain_simulator.blockchain.blockchain_p import BlockchainMProc, BlockchainStates


backup_autoproxy = multiprocessing.managers.AutoProxy

# Defining a new AutoProxy that handles unwanted key argument 'manager_owned'
def redefined_autoproxy(
    token,
    serializer,
    manager=None,
    authkey=None,
    exposed=None,
    incref=True,
    manager_owned=True,
):
    # Calling original AutoProxy without the unwanted key argument
    return backup_autoproxy(token, serializer, manager, authkey, exposed, incref)


# Updating AutoProxy definition in multiprocessing.managers package
multiprocessing.managers.AutoProxy = redefined_autoproxy

"""
# multiprocessing/managers.py
# By default, expose public methods, and property access is not supported
def all_methods(obj):
    '''
    Return a list of names of methods of `obj`
    '''
    temp = []
    for name in dir(obj):
        func = getattr(obj, name)
        if callable(func):
            temp.append(name)
    return temp

def public_methods(obj):
    '''
    Return a list of names of methods of `obj` which do not start with '_'
    '''
    return [name for name in all_methods(obj) if name[0] != '_']
"""


class BlockchainStatesManager(BaseManager):
    """
    Manager for Multi BlockchainStates
    """


class ProxyBase(NamespaceProxy):
    _exposed_ = ("__getattribute__", "__setattr__", "__delattr__")


BlockchainStatesManager.register("Dict", dict, DictProxy)
BlockchainStatesManager.register("BlockStorage", BlockStorage)
BlockchainStatesManager.register("TransactionIndexer", TransactionIndexer)
BlockchainStatesManager.register("BaseStore", BaseStore)
BlockchainStatesManager.register("SyncMemPool", SyncMemPool)


class BlockchainStatesProxy(NamespaceProxy):
    _exposed_ = tuple(dir(BlockchainStates))

    def __getattr__(self, name):
        result = super().__getattr__(name)
        if isinstance(result, types.MethodType):

            def wrapper(*args, **kwargs):
                # return self._callmethod(name, args, kwargs)
                return self._callmethod(name, args, kwargs)

            return wrapper
        return result


# Support property read and write
BlockchainStatesManager.register(
    "BlockchainStates", BlockchainStates, BlockchainStatesProxy
)

from typing import List, Dict, Callable
from chain_simulator.blockchain.blockchain_p import BlockchainStates
from chain_simulator.service_unix.tool.response import StandardResponse
from unix_server.server.server import Handler


class BlockchainHandler(Handler):
    def initialize(self, bcstates: BlockchainStates, **kwargs) -> None:
        assert isinstance(bcstates, BlockchainStates)
        self.bcstates = bcstates
        self.kwargs = kwargs

    @classmethod
    def routers(cls) -> Dict:
        routers = {
            r"/query_block": cls.query_block,
            r"/query_tx_proof": cls.query_tx_proof,
            r"/query_tx_receipt_proof": cls.query_tx_receipt_proof,
            r"/query_block_number": cls.query_block_number,
            r"/query_pool_count": cls.query_pool_count,
            r"/stop_mining": cls.stop_mining,
            r"/start_mining": cls.start_mining,
            r"/start_gen_xtx": cls.start_gen_xtx,
            r"/stop_gen_xtx": cls.stop_gen_xtx,
        }
        return routers

    def get(self):
        resp = StandardResponse()
        try:
            callfunc: callable = self.__get_func()
            result = callfunc(self)
            resp.set_code(200).set_msg(str(result))
        except Exception as e:
            resp.set_code(201).set_error(str(e))
        finally:
            self.write(resp.as_str())

    def post(self):
        resp = StandardResponse()
        try:
            callfunc: callable = self.__get_func()
            result = callfunc(self)
            resp.set_code(200).set_msg(str(result))
        except Exception as e:
            resp.set_code(201).set_error(str(e))
        finally:
            self.write(resp.as_str())

    def __get_func(self) -> callable:
        path = self.get_url()
        routers = self.routers()
        callfunc = routers.get(path, None)
        if callfunc is None:
            raise Exception("invalid uri:'{}'".format(path))
        return callfunc

    def stop_mining(self) -> bool:
        self.bcstates.stop_mining()
        return True

    def start_mining(self) -> bool:
        self.bcstates.start_mining()
        return True

    def start_gen_xtx(self) -> bool:
        self.bcstates.start_gen_xtx()
        return True

    def stop_gen_xtx(self) -> bool:
        self.bcstates.stop_gen_xtx()
        return True

    def query_block(self) -> str:
        bn: int = int(self.get_argument("bn"))
        block = self.bcstates.get_block_by_height(bn)
        if block is None:
            maxbn = self.bcstates.block_num()
            raise Exception(f"cannot find block: {bn}. max block number is {maxbn} ")

        return block.as_str()

    def query_block_number(self) -> int:
        return self.bcstates.block_num()

    def query_tx_proof(self) -> str:
        """get tx proof[hexStr] from blockchain by txhash

        :raises Exception: not find tx proof
        :return: proof which is hex str
        :rtype: str
        """
        txhash = self.get_argument("txhash")
        proof = self.bcstates.get_tx_proof(txhash)
        if proof is None:
            raise Exception(f"get no proof of {txhash}")
        return proof.hex()

    def query_tx_receipt_proof(self) -> str:
        """get tx receipt proof[hexStr] from blockchain by txhash

        :raises Exception: not find tx receipt proof
        :return: proof which is hex str
        :rtype: str
        """
        txhash = self.get_argument("txhash")
        proof = self.bcstates.get_tx_proof(txhash)
        if proof is None:
            raise Exception(f"get no proof of {txhash}")
        return proof.hex()

    def query_pool_count(self) -> int:
        return self.bcstates.txpool.size()

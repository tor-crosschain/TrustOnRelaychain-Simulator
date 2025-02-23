from chain_simulator.types.block import Block


class Context(object):
    def __init__(self) -> None:
        self.block: Block = None

    def set(self, block: Block) -> None:
        self.block = block

    def reset(self) -> None:
        self.block = None

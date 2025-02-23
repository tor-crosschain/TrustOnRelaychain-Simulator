from __future__ import annotations
import configparser
from typing import List, Optional


class XtxConfig:
    def __init__(self, *args, **kwargs) -> None:
        self.dstids = kwargs.get("dstids", [])
        self.classes = kwargs.get("classes", {})
        self.srcid = kwargs.get("srcid", -1)


class BaseConfig(object):
    def __init__(self, *args, **kwargs) -> None:
        self.block_size: int = kwargs.get("block_size", 100)
        self.block_interval: int = kwargs.get(
            "block_interval", 3
        )  # consensus interval by seconds
        self.mempool_size: int = kwargs.get("mempool_size", 5000)
        self.api_port: int = kwargs.get("api_port", 8888)
        self.execute_timeout = int(kwargs.get("execute_timeout", 1))
        self.execute_timeout_ns: int = self.execute_timeout * (10**9)
        self.gen_xtx_num: int = kwargs.get("gen_xtx_num", 0)
        self.xtx_config: XtxConfig = kwargs.get("xtx_config", XtxConfig())

    def read_from_file(self, cfg: BaseConfig, f: str) -> None:
        parser = configparser.ConfigParser()
        parser.read(f)
        cfg.block_interval = parser["block"].getint("interval")
        cfg.block_size = parser["block"].getint("size")
        cfg.mempool_size = parser["mempool"].getint("size")
        cfg.api_port = parser["api"].getint("port")

    @staticmethod
    def from_file(f: str) -> BaseConfig:
        cfg = BaseConfig()
        cfg.read_from_file(cfg, f)
        return cfg

class Config(BaseConfig):
    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self.api_port: int = kwargs.get("api_port", 8888)
    
    @staticmethod
    def from_file(f: str) -> Config:
        cfg = Config()
        cfg.read_from_file(cfg, f)
        return cfg

class ConfigUnix(BaseConfig):
    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self.socket_paths: List[str] = kwargs.get("socket_paths", [])
        self.max_workers: Optional[int] = kwargs.get("max_workers", None)
        self.max_conns: Optional[int] = kwargs.get("max_conns", None)
    
    @staticmethod
    def from_file(f: str) -> ConfigUnix:
        cfg = ConfigUnix()
        cfg.read_from_file(cfg, f)
        return cfg
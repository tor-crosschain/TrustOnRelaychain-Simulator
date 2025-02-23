from chain_simulator.config.config import Config


def test_from_file():
    f = "chain_simulator/config/tests/test_config.ini"
    cfg = Config.from_file(f)
    assert cfg.api_port == 8888
    assert cfg.block_interval == 3
    assert cfg.block_size == 10

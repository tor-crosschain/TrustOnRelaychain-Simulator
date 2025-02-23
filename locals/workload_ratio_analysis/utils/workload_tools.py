import os
from chain_simulator.config.config import XtxConfig
from utils.localtools import TestSetting


def gen_xtx_config(setting: TestSetting, chain_class):
    classes = ["Ethereum"] * chain_class[0] + ["Tendermint"] * chain_class[1]
    for idx in range(len(setting.para_configs)):
        setting.para_configs[idx].gen_xtx_num = 5
        setting.para_configs[idx].xtx_config = XtxConfig(
            dstids=list(range(0, idx)) + list(range(idx + 1, setting.chainnum)),
            srcid=idx,
            classes=classes,
        )


def update_basic_setting(setting: TestSetting):
    classone = setting.chainnum // 2
    classtwo = setting.chainnum - classone
    gen_xtx_config(setting, chain_class=[classone, classtwo])
    setting.indicate_filepath = os.path.join(
        setting.output_indicate_dir,
        f"{setting.ccmode}-{setting.chainnum}-{setting.para_configs[0].gen_xtx_num}.json",
    )
    setting.workload_filepath = os.path.join(
        setting.output_workload_dir,
        f"{setting.ccmode}-{setting.chainnum}-{setting.para_configs[0].gen_xtx_num}.json",
    )

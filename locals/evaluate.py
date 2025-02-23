import os, sys

sys.path.insert(0, os.path.abspath("."))
import time
import asyncio
from utils.localtools import get_args, TestSetting
from locals.aor import test_aor_async
from locals.tor import test_tor_async
from locals.nor import test_nor_async

test_funcs = {"ToR": test_tor_async, "AoR": test_aor_async, "NoR": test_nor_async}

if __name__ == "__main__":
    cmdargs = get_args()
    test_setting = TestSetting.new(cmdargs)
    starttime = time.perf_counter()
    test_func = test_funcs[test_setting.ccmode]
    asyncio.run(test_func(test_setting))
    endtime = time.perf_counter()
    print(f"time cost: {endtime-starttime}")

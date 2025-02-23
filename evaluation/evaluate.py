"""
Send transactions to the constructed cross-chain network

Monitor destination chain transactions, and start calculating TPS and Latency 
when destination chain transactions reach the specified value
"""
import multiprocessing
import requests
import random
import json
import time
import sys, os
import yaml
import argparse

sys.path.insert(0, os.path.abspath("."))
from typing import List, Tuple
from collections import Counter
from chain_simulator.config.config import Config
from chain_simulator.types.block import Block
from chain_simulator.types.transaction import TranMemo
from relayer.connector.connector import Connector

DEPLOYEDHOSTS_PATH = "./ansible/deployedhosts"
GLOBALVARS_PATH = "./ansible/vars/main.yml"
PARACONFIG_PATH = "./ansible/configs/parachain"


def send_tx(
    test_id: str,
    chainnum: int,
    classes: List[str],
    paraid: int,
    host: str,
    ccmode: str,
    txnum: int,
    xtxnum: int,
    costsend: multiprocessing.Value,
    first_init: multiprocessing.Value,
    random_send: bool = True,
) -> None:
    # Transaction destination chain identifiers. If identifier is -1, it's a normal transaction
    # If identifier is not 0, it's a cross-chain transaction, and this identifier is the destination chain identifier
    dsts = [1] * xtxnum + [-1] * (txnum - xtxnum)
    dsts = random.sample(dsts, len(dsts))
    xtx_cnt = 0
    for i in range(len(dsts)):
        if dsts[i] == 1:
            x = None
            while True:
                if random_send:
                    # Randomly select target chain identifier
                    x = random.randint(0, chainnum - 1)
                    if x != paraid: 
                        break
                else:
                    # Send in order to the target chain
                    xtx_cnt = (xtx_cnt + 1) % chainnum
                    if xtx_cnt == paraid:
                        xtx_cnt = (xtx_cnt + 1) % chainnum
                    x = xtx_cnt
                    break
            assert x is not None
            dsts[i] = x
    url_send_tx = f"http://{host}/send_tx"
    costall = 0
    min_init = 0
    for idx in range(txnum):
        retry = 3
        for i in range(retry):
            try:
                if dsts[idx] >= 0:  # check if it's a cross-chain transaction
                    # Send transaction to the app_init function of the lightclient contract
                    dstid = int(dsts[idx])
                    memo = {"type": TranMemo.CTXSRC, "dst": dsts[idx]}
                    memo["ID"] = test_id
                    # Source chain timestamp
                    initime = time.time()
                    memo["ts"] = {"init": initime}
                    if min_init == 0:
                        min_init = initime
                    data = {
                        "tx": {
                            "sender": f"send/{paraid}/{idx}",
                            "to": "lightclient",
                            "data": json.dumps(
                                {
                                    "func": "app_init",
                                    "arguments": [
                                        dstid,
                                        classes[dstid],
                                        "crosschain-data",
                                    ],
                                }
                            ),
                            "memo": json.dumps(memo),
                        }
                    }
                else:
                    memo = {"type": "TX"}
                    memo["ID"] = test_id
                    # Source chain timestamp
                    memo["ts"] = {"init": time.time()}
                    data = {
                        "tx": {
                            "sender": f"send/{paraid}/{idx}",
                            "to": "base",
                            "data": json.dumps({"arguments": [f"a{idx}", idx]}),
                            "memo": json.dumps(memo),
                        }
                    }
                start = time.time()
                resp_send_tx = requests.post(
                    url=url_send_tx, data=json.dumps(data), timeout=10
                )

            except Exception as e:
                if i == retry - 1:
                    raise Exception(f"{str(e)}")
                time.sleep(1)
                continue

            assert resp_send_tx.status_code == 200
            resp = json.loads(resp_send_tx.text)
            assert resp["error"] == "", f"response error: {resp['error']}"
            assert resp["code"] == 200, f"response code: {resp['code']}"
            endtime = time.time()
            costall += int((endtime - start) * 1000)
            break


    with costsend.get_lock():
        costsend.value += costall

    with first_init.get_lock():
        if first_init.value == 0:
            first_init.value = min_init
        else:
            first_init.value = min(first_init.value, min_init)


def send_tx_parallelism(
    test_id: str,
    hosts: List[str],
    ccmode: str,
    classes: List[str],
    txnum: int,
    xtxnum: int,
    random_send: bool,
) -> List[multiprocessing.Process]:
    procs: List[multiprocessing.Process] = []
    costsend = multiprocessing.Value("d", 0)
    first_init = multiprocessing.Value("d", 0)
    for paraid, host in enumerate(hosts):
        proc = multiprocessing.Process(
            target=send_tx,
            args=(
                test_id,
                len(hosts),
                classes,
                paraid,
                host,
                ccmode,
                txnum,
                xtxnum,
                costsend,
                first_init,
                random_send,
            ),
        )
        procs.append(proc)

    for proc in procs:
        proc.start()

    # Wait for transaction sending to finish
    for proc in procs:
        proc.join()
    print("============process sendtx finished!")

    cost = costsend.value
    cost_avg = cost / (len(hosts) * txnum)
    return procs, cost_avg, first_init.value


def safe_req(url: str, params: dict, method: str = "GET") -> requests.Response:
    assert method in ["GET", "POST"]
    retry = 5
    for i in range(retry):
        try:
            if method == "GET":
                r = requests.get(url=url, params=params, timeout=10)
            else:
                r = requests.post(url=url, data=params, timeout=10)
            return r
        except Exception as e:
            time.sleep(1)
    raise Exception(f"requests failed! url: {url}")


def check(
    test_id: str,
    idx: int,
    host: str,
    start_bn: int,
    val,
    target: int,
    min_init,
    max_last_commit,
    latency_sum,
    ctxs: multiprocessing.Queue,
):
    tempctxs = []
    assert isinstance(host, str)
    assert isinstance(target, int)
    url = f"http://{host}/query_block_number"
    r = requests.get(url)
    resp = json.loads(r.text)
    bn = int(resp["msg"])
    i = start_bn
    while True:
        if i > bn:
            while True:
                url = f"http://{host}/query_block_number"
                r = safe_req(url, params=None, method="GET")
                resp = json.loads(r.text)
                bn = int(resp["msg"])
                if i <= bn:
                    break
                time.sleep(5)
        url_block = f"http://{host}/query_block?bn={i}"
        r = safe_req(url_block, params=None, method="GET")
        resp = json.loads(r.text)
        blk: dict = json.loads(resp["msg"])
        assert blk["height"] == i
        block = Block.from_json(blk)
        txs = block.txs
        for tx in txs:
            memo = json.loads(tx.memo)
            if memo["type"] == TranMemo.CTXDST and memo["ID"] == test_id:
                tempctxs.append(memo)
                last_commit = memo["ts"]["commit"][-1]
                init = memo["ts"]["init"]
                with latency_sum.get_lock():
                    latency_sum.value += last_commit - init
                with min_init.get_lock():
                    if min_init.value > init:
                        min_init.value = init
                with max_last_commit.get_lock():
                    if max_last_commit.value < last_commit:
                        max_last_commit.value = last_commit
                with val.get_lock():
                    val.value += 1
                    if val.value >= target:
                        break
        with val.get_lock():
            if val.value >= target:
                print(f"val.value reached: {val.value}")
                break
        i += 1
        print(f"val.value: {val.value}, target: {int(target)}")
    print(f"{multiprocessing.current_process().name} put")
    ctxs.put(json.dumps(tempctxs))
    print(f"{multiprocessing.current_process().name} put ok")


def query_latest_bns(hosts: List[str]) -> List[int]:
    bns = []
    for host in hosts:
        url = f"http://{host}/query_block_number"
        r = requests.get(url)
        resp = json.loads(r.text)
        bn = int(resp["msg"])
        bns.append(bn)
    return bns


def readhosts() -> [List[str], dict]:
    with open(DEPLOYEDHOSTS_PATH, "r") as f:
        hoststr = f.read()
        data: dict = yaml.load(hoststr, Loader=yaml.Loader)
        parahosts = data["parahosts"].split(",")
        parahosts[-1] = parahosts[-1].rstrip("\n")
        interhost = data.get("interhost", "")
        ccmode = data.get("ccmode", "NoR")

    classes = []
    for host in parahosts:
        starttime = time.time()
        classes.append(Connector(host=host).paratype)
        endtime = time.time()
        print(f"{host} cost: {endtime-starttime}")

    paraconf = {}
    with open(PARACONFIG_PATH, "r") as f:
        for line in f.readlines():
            line = line.lstrip("--")
            plc = line.find("=")
            key = line[:plc]
            value = line[plc + 1 :].rstrip("\n")
            paraconf[key] = value

    return parahosts, ccmode, interhost, paraconf, classes


def query_inter_workload(interhost: str, startheight: int) -> [int, float]:
    cnct = Connector(host=interhost)
    maxbn = cnct.query_block_number()
    txnums = 0
    print(f"query inter block from {startheight} to {maxbn+1}")
    starttime = 0
    endtime = 0
    for i in range(startheight, maxbn + 1):
        block: Block = cnct.query_block(i)
        txnums += len(block.txs)
        if i == startheight:
            starttime = block.timestamp
        elif i == maxbn:
            endtime = block.timestamp
    return txnums, endtime - starttime


def analysis_tor(memos: List[dict]) -> dict:
    ts_src = []
    ts_rly = []
    ts_dst = []
    for memo in memos:
        ts = memo["ts"]
        ts_src.append(ts["commit"][0] - ts["init"])
        rly = ts["relayer"]
        assert rly[2][0] == "send", f"relayer ts tag({rly[2][0]}) is invalid"
        assert rly[0][0] == "listened", f"relayer ts tag({rly[0][0]}) is invalid"
        ts_rly.append(ts["relayer"][2][1] - ts["relayer"][0][1])
        ts_dst.append(ts["commit"][1] - ts["relayer"][2][1])
    ts_src_avg = sum(ts_src) / len(ts_src)
    ts_rly_avg = sum(ts_rly) / len(ts_rly)
    ts_dst_avg = sum(ts_dst) / len(ts_dst)
    return {
        "ts_src_avg": ts_src_avg,
        "ts_rly_avg": ts_rly_avg,
        "ts_dst_avg": ts_dst_avg,
    }


def analysis_nor(memos: List[dict]) -> dict:
    ts_src = []
    ts_rly = []
    ts_dst = []
    for memo in memos:
        ts = memo["ts"]
        ts_src.append(ts["commit"][0] - ts["init"])
        rly = ts["relayer"]
        assert rly[2][0] == "send", f"relayer ts tag({rly[2][0]}) is invalid"
        assert rly[0][0] == "listened", f"relayer ts tag({rly[0][0]}) is invalid"
        ts_rly.append(ts["relayer"][2][1] - ts["relayer"][0][1])
        ts_dst.append(ts["commit"][1] - ts["relayer"][2][1])
    ts_src_avg = sum(ts_src) / len(ts_src)
    ts_rly_avg = sum(ts_rly) / len(ts_rly)
    ts_dst_avg = sum(ts_dst) / len(ts_dst)
    return {
        "ts_src_avg": ts_src_avg,
        "ts_rly_avg": ts_rly_avg,
        "ts_dst_avg": ts_dst_avg,
    }


def analysis_aor(memos: List[dict]) -> dict:
    ts_src = []
    ts_rly01 = []
    ts_inter = []
    ts_rly02 = []
    ts_dst = []
    for memo in memos:
        ts = memo["ts"]
        ts_src.append(ts["commit"][0] - ts["init"])
        rly = ts["relayer"]
        ts_rly01.append(rly[2][1] - rly[0][1])
        ts_inter.append(ts["commit"][1] - rly[2][1])
        ts_rly02.append(rly[5][1] - rly[3][1])
        ts_dst.append(ts["commit"][2] - rly[5][1])
    ts_src_avg = sum(ts_src) / len(ts_src)
    ts_rly01_avg = sum(ts_rly01) / len(ts_rly01)
    ts_inter_avg = sum(ts_inter) / len(ts_inter)
    ts_rly02_avg = sum(ts_rly02) / len(ts_rly02)
    ts_dst_avg = sum(ts_dst) / len(ts_dst)
    return {
        "ts_src_avg": ts_src_avg,
        "ts_rly01_avg": ts_rly01_avg,
        "ts_inter_avg": ts_inter_avg,
        "ts_rly02_avg": ts_rly02_avg,
        "ts_dst_avg": ts_dst_avg,
    }


def analysis(ccmode: str, memos: List[dict]) -> dict:
    if ccmode == "ToR":
        return analysis_tor(memos)
    if ccmode == "AoR":
        return analysis_aor(memos)
    if ccmode == "NoR":
        return analysis_nor(memos)
    else:
        raise Exception(f"invalid ccmode({ccmode})")


def listen_inter_load(
    interhost: str,
    inter_bn: int,
    inter_load_queue: multiprocessing.Queue,
    inter_load_event: multiprocessing.Event,
):
    url = f"http://{interhost}/query_pool_count"
    while True:
        if inter_load_event.is_set():
            break
        res = requests.get(url)
        assert res.status_code == 200
        response = json.loads(res.text)
        assert response["code"] == 200
        mpcount = int(response["msg"])
        inter_load_queue.put(mpcount)
        time.sleep(1)


def execute(
    txnum: int,
    xtxratio: int,
    xtxnum: int,
    check_ratio: float,
    random_send: bool,
    isevaluate: bool,
):

    test_id = f"{int(time.time()*1000)}"

    hosts, ccmode, interhost, paraconf, classes = readhosts()
    print(f"paranum: {len(hosts)}")
    print(f"parahosts: {hosts}")
    print(f"ccmode: {ccmode}")
    print(f"interhost: {interhost}")
    print(f"paraconf: {paraconf}")
    print(f"ratio_eth: {Counter(classes)['Ethereum']/len(classes)}")

    start_bns = [x + 1 for x in query_latest_bns(hosts)]
    inter_bn = 1
    if ccmode in ["ToR", "AoR"]:
        inter_bns = query_latest_bns([interhost])
        inter_bn = inter_bns[0] + 1
    print(start_bns)

    # Listen to the load on the relay chain, collect the number of transactions in the pool every second
    listen_inter_load_proc = None
    inter_load_queue = None
    inter_load_event = None
    if ccmode in ["ToR", "AoR"] and isevaluate:
        inter_load_queue = multiprocessing.Manager().Queue()
        inter_load_event = multiprocessing.Manager().Event()
        listen_inter_load_proc = multiprocessing.Process(
            target=listen_inter_load,
            args=(interhost, inter_bn, inter_load_queue, inter_load_event),
        )
        listen_inter_load_proc.start()

    # Send transactions to each parallel chain in parallel
    procs_sendtx, costsend_avg, min_tx_initime = send_tx_parallelism(
        test_id, hosts, ccmode, classes, txnum, xtxnum, random_send
    )

    # Check if the number of transactions with memo.type == CTX-DST on all chains is the same as the number of cross-chain transactions
    target = int(xtxnum * len(hosts) * check_ratio)
    check_procs = []
    val = multiprocessing.Value("i", 0)
    min_init = multiprocessing.Value("d", time.time() * 2)
    max_last_commit = multiprocessing.Value("d", 0)
    latency_sum = multiprocessing.Value("d", 0)
  
    ctxs = multiprocessing.Manager().Queue(maxsize=10000000)
    for idx, host in enumerate(hosts):
        proc = multiprocessing.Process(
            target=check,
            args=(
                test_id,
                idx,
                host,
                start_bns[idx],
                val,
                target,
                min_init,
                max_last_commit,
                latency_sum,
                ctxs,
            ),
        )
        check_procs.append(proc)
    for proc in check_procs:
        proc.start()
    for proc in check_procs:
        proc.join()

    inter_loads = []
    inter_loads_filename = ""
    if ccmode in ["ToR", "AoR"] and isevaluate:
        inter_load_event.set()
        listen_inter_load_proc.join()
        print("inter load listen process stop!")
        while True:
            if inter_load_queue.empty():
                break
            data = inter_load_queue.get()
            inter_loads.append(data)
            inter_load_queue.task_done()
        filedir = "temp/result/interloads"
        if not os.path.exists(filedir):
            os.makedirs(filedir)
        inter_loads_filename = os.path.join(filedir, f"{int(time.time()*1000)}.json")
        json.dump(inter_loads, open(inter_loads_filename, "w"))  # TODO write to file

    # Get total number of transactions on the relay chain
    interalltx = 0
    interdur = 1.0
    if ccmode in ["ToR", "AoR"] and isevaluate:
        print("查询中继链 workload...")
        interalltx, interdur = query_inter_workload(interhost, inter_bn)
        print("查询完成")

    # Analyze the delay of each stage
    memos = []
    while not ctxs.empty():
        memos.extend(json.loads(ctxs.get()))
    measurments = analysis(ccmode, memos)

    # # DEBUG begin
    # json.dump(memos, open("temp/memos.json", 'w'))
    # # DEBUG end

    # Calculate throughput and average delay
    # The time used for throughput is: the time from the first transaction to the last transaction
    # The average delay is: the average value of the interaction delay of each cross-chain transaction
    TPS_0 = (
        int(paraconf["block_size"]) / int(paraconf["block_interval"]) * len(hosts) // 2
    )
    tps = target / (max_last_commit.value - min_init.value)
    latency_avg = latency_sum.value / target

    print(f"send cost avg: {costsend_avg}")
    print(f"min_init: {min_init.value}, first_init: {min_tx_initime}")
    data = {
        "ccmode": ccmode,
        "para_num": len(hosts),
        "xtx_ratio": xtxratio,
        "interalltxs": interalltx,
        "interdur": interdur,
        "tps": tps,
        "tps_ratio": "{:.2f}%".format((tps / TPS_0) * 100),
        "latency_avg": latency_avg,
        "min_init": min_init.value,
        "first_init": min_tx_initime,
        "inter_loads": inter_loads_filename,
    }
    data.update(measurments)
    return data


def get_args():
    parser = argparse.ArgumentParser()
    parser.add_argument("--loop", type=int, default=5)
    parser.add_argument("--xtxratios", nargs="+", type=float)
    return parser.parse_args()


def run(ctx_ratio: float) -> dict:
    print("============================================================")
    print("*                  break last cross-txs                    *")
    print("============================================================")
    hosts, *_ = readhosts()
    txnum0 = len(hosts) - 1  # Send one cross-chain transaction to each chain
    xtxratio0 = 1
    xtxnum0 = int(txnum0 * xtxratio0)  # Number of cross-chain transactions
    check_ratio0 = 1
    execute(
        txnum=txnum0,
        xtxratio=xtxratio0,
        xtxnum=xtxnum0,
        check_ratio=check_ratio0,
        random_send=False,
        isevaluate=False,
    )
    print("==================== break finished ========================")
    print("||                                                        ||")
    print("||                                                        ||")
    print("||                                                        ||")
    print("||********************************************************||")
    print("||                                                        ||")
    print("||                                                        ||")
    print("||                                                        ||")
    print("============================================================")
    print("*                   evalutation start                      *")
    print("============================================================")
    txnum = 500  # Total number of transactions
    xtxratio = ctx_ratio
    xtxnum = int(txnum * xtxratio)  # Number of cross-chain transactions
    check_ratio = 0.95
    result = execute(
        txnum=txnum,
        xtxratio=xtxratio,
        xtxnum=xtxnum,
        check_ratio=check_ratio,
        random_send=True,
        isevaluate=True,
    )
    print("==================== evalutation end =======================")
    return result


def main():
    args = get_args()
    loop_cnt = int(args.loop)
    xtxratios = args.xtxratios

    temp_dir = "temp/result"
    if not os.path.exists(temp_dir):
        os.makedirs(temp_dir)

    for xtxratio in xtxratios:
        filename = f"{str(xtxratio).replace('.', '_')}.json"
        result_file = os.path.join(os.path.abspath(temp_dir), filename)
        results = []
        for i in range(loop_cnt):
            print("============================================================")
            print("*                                                          *")
            print(
                f"*                 xtxratio: {xtxratio}, loop: {i}                   *"
            )
            print("*                                                          *")
            print("============================================================")
            result = run(xtxratio)
            results.append(result)
            json.dump(results, open(result_file, "w"))


if __name__ == "__main__":
    main()

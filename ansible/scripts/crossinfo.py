import time
import requests
import json
import sys
import os

sys.path.insert(0, os.path.abspath("."))
from typing import List


def set_paraid(host: str, paraid: int) -> str:
    print(f"set paraid({paraid})")
    url_set_id = f"http://{host}/send_tx"
    memo = {"type": "TX"}
    data = {
        "tx": {
            "sender": f"send/{paraid}/{set}",
            "to": "lightclient",
            "data": json.dumps({"func": "set_paraid", "arguments": [paraid]}),
            "memo": json.dumps(memo),
        }
    }
    resp_send_tx = requests.post(url_set_id, data=json.dumps(data), timeout=10)
    assert resp_send_tx.status_code == 200
    resp = json.loads(resp_send_tx.text)
    assert resp["error"] == "", f"response error: {resp['error']}"
    assert resp["code"] == 200, f"response code: {resp['code']}"
    return resp["msg"]  # 返回哈希


def set_paratype(host: str, paratype: str):
    print(f"set paratype({paratype})")
    url_set_type = f"http://{host}/send_tx"
    memo = {"type": "TX"}
    data = {
        "tx": {
            "sender": f"send/{paratype}/{set}",
            "to": "lightclient",
            "data": json.dumps({"func": "set_paratype", "arguments": [paratype]}),
            "memo": json.dumps(memo),
        }
    }
    resp_send_tx = requests.post(url_set_type, data=json.dumps(data), timeout=10)
    assert resp_send_tx.status_code == 200
    resp = json.loads(resp_send_tx.text)
    assert resp["error"] == "", f"response error: {resp['error']}"
    assert resp["code"] == 200, f"response code: {resp['code']}"
    return resp["msg"]  # 返回哈希


def set_crossinfo(host: str, chain_id: int, chain_type: str):

    print(f"set crossinfo === ")

    def wait(*hashes, timeout=30):
        """等待交易被打包到区块中"""
        for hs in hashes:
            print(f"wait txhash: {hs}")
            url = f"http://{host}/query_tx"
            params = {"txhash": hs}
            starttime = time.time()
            while True:
                if time.time() - starttime > timeout:
                    raise Exception(f"wait txhash timeout! txhash: {hs}")
                try:
                    res = requests.get(url, params=params)
                    print(f"full url: {res.url}")
                    assert res.status_code == 200
                    resp = json.loads(res.text)
                    assert resp["code"] == 200, f"response code: {resp['code']}"
                    print("get!")
                    break
                except:
                    time.sleep(3)
                finally:
                    pass

    hash_id = set_paraid(host, chain_id)
    hash_type = set_paratype(host, chain_type)
    wait(hash_id, hash_type)


def get_args():
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument("--host", type=str, required=True)
    parser.add_argument("--chain_id", type=int, required=True)
    parser.add_argument("--chain_type", type=str, required=True)
    return parser.parse_args()


def main():
    args = get_args()
    host = args.host
    chain_id = args.chain_id
    chain_type = args.chain_type
    set_crossinfo(host, chain_id, chain_type)


if __name__ == "__main__":
    main()

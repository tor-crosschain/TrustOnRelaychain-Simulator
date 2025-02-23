import requests
import time
import json
import sys, os

sys.path.insert(0, os.path.abspath("."))
from collections import Counter
from evaluation.evaluate import readhosts


def main():
    hosts, ccmode, interhost, paraconf, classes = readhosts()
    print(f"paranum: {len(hosts)}")
    print(f"parahosts: {hosts}")
    print(f"ccmode: {ccmode}")
    print(f"interhost: {interhost}")
    print(f"paraconf: {paraconf}")
    print(f"ratio_eth: {Counter(classes)['Ethereum']/len(classes)}")

    if interhost != "":
        hosts.append(interhost)
    que_cnt = 0
    while True:
        for idx, host in enumerate(hosts):
            url = f"http://{host}/query_pool_count"
            res = requests.get(url)
            assert res.status_code == 200
            response = json.loads(res.text)
            msg = response["msg"]
            if idx == len(hosts) - 1:
                print("interhost: ")
            print(f"{host}: {msg}")
        que_cnt += 1
        print(f"==========={que_cnt}===========")
        time.sleep(5)


if __name__ == "__main__":
    main()

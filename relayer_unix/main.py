import multiprocessing
import time
import requests
import json
import sys
import os

sys.path.insert(0, os.path.abspath("."))
from typing import List, Tuple
from relayer.connector.connector import Connector
from relayer.relayer.relayer import Relayer, Mode, ToRRelayerType


def build_relayers(
    this_idx: int, hosts: List[str], ccmode: str, interhost: str
) -> List[Relayer]:

    relayers = []
    if this_idx == 30000:
        # idx == 30000: relay chain
        # the relay chain connects to the parallel chain
        assert ccmode in ["ToR", "AoR"], f"ccmode({ccmode}) must be ToR or AoR"
        if ccmode == "AoR":
            rlytp = None
            mode = Mode.MODEAOR
        else:
            rlytp = ToRRelayerType.PAR
            mode = Mode.MODETOR
        lh = len(hosts)

        for i in range(lh):
            src_connector = Connector(
                host=interhost, sender=f"proc/inter/inter/inter", isinter=True
            )
            tgt_connector = Connector(host=hosts[i], sender=f"proc/inter/{i}/dst")
            relayer = Relayer(src_connector, tgt_connector, mode=mode, rlytp=rlytp)
            relayers.append(relayer)
            print(f"build relayer between ({relayer.src.pid}, {relayer.dst.pid})")
            assert relayer.src.pid == this_idx, f"inter pid is { relayer.src.pid }"
            assert relayer.dst.pid == i, f"dst pid is { relayer.dst.pid }"
        return relayers

    # parallel chain connects to parallel chain, relay chain(AoR, ToR)
    this_host = hosts[this_idx]
    if ccmode == "NoR":
        lh = len(hosts)
        for i in range(lh):
            if this_host == hosts[i]:
                continue
            src_connector = Connector(
                host=this_host, sender=f"proc/{this_idx}/{this_idx}/src"
            )
            tgt_connector = Connector(host=hosts[i], sender=f"proc/{this_idx}/{i}/dst")
            relayer = Relayer(src_connector, tgt_connector, mode=Mode.MODENOR)
            relayers.append(relayer)
            print(f"build relayer between ({relayer.src.pid}, {relayer.dst.pid})")
            assert relayer.src.pid == this_idx, f"src pid is { relayer.src.pid }"
            assert relayer.dst.pid == i, f"dst pid is { relayer.dst.pid }"
    elif ccmode == "AoR":
        src_connector = Connector(
            host=this_host, sender=f"proc/{this_idx}/{this_idx}/src"
        )
        dst_connector = Connector(
            host=interhost, sender=f"proc/{this_idx}/inter/inter", isinter=True
        )
        relayer = Relayer(src_connector, dst_connector, mode=Mode.MODEAOR)
        assert relayer.src.pid == this_idx, f"src pid is { relayer.src.pid }"
        assert (
            relayer.dst.pid == 30000
        ), f"inter pid is { relayer.dst.pid }"  # relay chain id is 30000
        relayers.append(relayer)
    elif ccmode == "ToR":
        src_connector = Connector(
            host=this_host, sender=f"proc/{this_idx}/{this_idx}/src"
        )
        dst_connector = Connector(
            host=interhost, sender=f"proc/{this_idx}/inter/inter", isinter=True
        )
        relayer = Relayer(
            src_connector, dst_connector, mode=Mode.MODETOR, rlytp=ToRRelayerType.PAR
        )
        assert (
            relayer.dst.pid == 30000
        ), f"inter pid is { relayer.dst.pid }"  # relay chain id is 30000
        relayers.append(relayer)
        lh = len(hosts)
        for i in range(lh):
            if this_host == hosts[i]:
                continue
            src_connector = Connector(
                host=this_host, sender=f"proc/{this_idx}/{this_idx}/src"
            )
            tgt_connector = Connector(host=hosts[i], sender=f"proc/{this_idx}/{i}/dst")
            inter_connector = Connector(
                host=interhost, sender=f"proc/{this_idx}/inter/inter", isinter=True
            )
            relayer = Relayer(
                src_connector,
                tgt_connector,
                mode=Mode.MODETOR,
                inter=inter_connector,
                rlytp=ToRRelayerType.PAP,
            )
            relayers.append(relayer)
            print(f"build relayer between ({relayer.src.pid}, {relayer.dst.pid})")
            assert relayer.src.pid == this_idx, f"src pid is { relayer.src.pid }"
            assert relayer.dst.pid == i, f"dst pid is { relayer.dst.pid }"
    else:
        raise Exception(f"invalid ccmode({ccmode})")

    return relayers


def start_relayers(idx: int, hosts: List[str], ccmode: str, interhost: str):

    print(f"start relayer({idx}), host={hosts[idx] if idx != 30000 else interhost}")

    # build relayer
    relayers = build_relayers(idx, hosts, ccmode, interhost)

    # start relay process
    procs_rly: List[multiprocessing.Process] = []
    for rly in relayers:
        proc = multiprocessing.Process(
            target=rly.start_one_way, name=f"relayer:<{rly.src.host},{rly.dst.host}>"
        )
        procs_rly.append(proc)

    return procs_rly, relayers


def get_args():
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument("--idx", type=int, required=True)
    parser.add_argument("--hosts", nargs="+", required=True)
    parser.add_argument(
        "--ccmode", type=str, default="NoR", choices=["NoR", "ToR", "AoR"]
    )
    parser.add_argument("--interhost", type=str, default="")
    return parser.parse_args()


def main():
    args = get_args()
    assert (
        len(args.hosts) > args.idx or args.idx == 30000
    ), f"hosts length({len(args.hosts)}) must be larger than idx({args.idx})"
    assert args.ccmode in ["NoR", "ToR", "AoR"], f"invalid ccmode({args.ccmode})"
    if args.ccmode in ["ToR", "AoR"]:
        assert (len(args.interhost) > 0, f"invalid interhost({args.interhost})!")

    for host in args.hosts:
        comp = host.split(":")
        assert len(comp) == 2, "hosts should only one ':'"

    idx = args.idx
    hosts = args.hosts
    ccmode = args.ccmode
    interhost = args.interhost

    print(f"get args.idx: {idx}")
    print(f"get args.hosts length: {len(hosts)}")
    print(f"get args.ccmode: {ccmode}")
    print(f"get args.interhost: {interhost}")

    procs_rly, _ = start_relayers(idx, hosts, ccmode, interhost)

    for proc in procs_rly:
        proc.start()
        print(f"start relayer: {proc.name}")
    for proc in procs_rly:
        proc.join()


if __name__ == "__main__":
    main()

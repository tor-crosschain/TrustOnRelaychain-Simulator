import os
import math
import json
from matplotlib import pyplot as plt
from matplotlib.patches import ConnectionPatch

datapath = "./locals/output/indicates"

output_dir = "./locals/plot"

workload_optimization_ratio = lambda x: (500 / x) / (
    1 + (500 / x)
)  


def output_path(img_name: str) -> str:
    return os.path.join(os.path.abspath(output_dir), img_name)


class Data:
    def __init__(self) -> None:
        self.pn_rt_tor = {}
        self.pn_rt_aor = {}
        self.pn_rt_nor = {}
        self.rt_pn_tor = {}
        self.rt_pn_aor = {}
        self.rt_pn_nor = {}
        self.read()
        self.average()

    def read(self):
        readfuncs = {"ToR": self.read_tor, "NoR": self.read_nor, "AoR": self.read_aor}
        for filename in os.listdir(datapath):
            eles = filename.split("-")
            if eles[0] not in ["ToR", "AoR", "NoR"]:
                continue
            ccmode, chain_num, _, xtxratio = eles
            chain_num = int(chain_num)
            xtxratio = int(xtxratio.split(".")[0]) / 100
            filepath = os.path.join(datapath, filename)
            readfuncs[ccmode](filepath, chain_num, xtxratio)

    def average(self):
        """
        read() function puts multiple experimental results of the same indicator into an array
        average() calculates the average value of the data for the same indicator
        """
        for pn, rt in self.pn_rt_tor.items():
            for ratio, data in rt.items():
                for key, value in data.items():
                    if key in ["workloads"]:
                        continue
                    sample = sorted(value)
                    if len(sample) > 1:
                        sample = sample[:-1]
                    data[key] = float(f"{sum(sample)/len(sample):.3f}")
                self.pn_rt_tor[pn][ratio] = data
                self.rt_pn_tor[ratio][pn] = data

        for pn, rt in self.pn_rt_aor.items():
            for ratio, data in rt.items():
                for key, value in data.items():
                    if key in ["workloads"]:
                        continue
                    sample = sorted(value)
                    if len(sample) > 1:
                        sample = sample[:-1]
                    data[key] = float(f"{sum(sample)/len(sample):.3f}")
                self.pn_rt_aor[pn][ratio] = data
                self.rt_pn_aor[ratio][pn] = data

        for pn, rt in self.pn_rt_nor.items():
            for ratio, data in rt.items():
                for key, value in data.items():
                    if key in ["workloads"]:
                        continue
                    sample = sorted(value)
                    if len(sample) > 1:
                        sample = sample[:-1]
                    data[key] = float(f"{sum(sample)/len(sample):.3f}")
                self.pn_rt_nor[pn][ratio] = data
                self.rt_pn_nor[ratio][pn] = data

    def read_tor(self, filepath: str, chain_num: int, xtxratio: float):
        item = json.load(open(filepath, "r"))
        pn = item["para_num"]
        assert pn == chain_num, f"pn({pn}) != chainnum({chain_num})"
        rt = item["xtx_ratio"]
        assert rt == xtxratio, f"rt({rt}) != xtxratio({xtxratio})"
        interalltxs = item["interalltxs"]
        interdur = item.get("interdur", 0)  # 中继链上的全部处理时间
        tps = item["tps"]
        latency_avg = item["latency_avg"]
        ts_src_avg = item["ts_src_avg"]
        ts_rly_avg = item["ts_rly_avg"]
        ts_dst_avg = item["ts_dst_avg"]
        workload_file = item["workload_file"]
        workloads = json.load(open(workload_file, "r"))

        paral_loads_avg = []
        paral_loads_max = []
        paral_bns_avg = []

        for paral_chain, paral_loads in workloads.items():
            if paral_chain == "30000":
                continue
       
            paral_loads_avg.append(sum(paral_loads[:9]) / 9)
            paral_loads_max.append(max(paral_loads))
            paral_bns_avg.append(len(paral_loads))

        paral_load_avg = sum(paral_loads_avg) / len(paral_loads_avg)
        paral_load_max = max(paral_loads_max)
        paral_bn_avg = sum(paral_bns_avg) / len(paral_bns_avg)

        inter_loads = workloads["30000"]
        inter_load_avg = sum(inter_loads) / len(inter_loads)
        inter_load_max = max(inter_loads)
        if self.pn_rt_tor.get(pn, None) is None:
            self.pn_rt_tor[pn] = {}
        if self.pn_rt_tor[pn].get(rt, None) is None:
            self.pn_rt_tor[pn][rt] = {
                "interalltxs": [],
                "interdur": [],
                "intertps": [],
                "tps": [],
                "latency_avg": [],
                "ts_src_avg": [],
                "ts_rly_avg": [],
                "ts_dst_avg": [],
                "inter_load_avg": [],
                "inter_load_max": [],
                "paral_load_avg": [],
                "paral_load_max": [],
                "paral_bn_avg": [],
                "workload_opt_ratio": [],
            }

        data = self.pn_rt_tor[pn][rt]
        data["interalltxs"].append(interalltxs)
        data["interdur"].append(interdur)
        data["intertps"].append(0 if int(interdur) == 0 else interalltxs / interdur)
        data["tps"].append(tps)
        data["latency_avg"].append(latency_avg)
        data["ts_src_avg"].append(ts_src_avg)
        data["ts_rly_avg"].append(ts_rly_avg)
        data["ts_dst_avg"].append(ts_dst_avg)
        data["inter_load_avg"].append(inter_load_avg)
        data["inter_load_max"].append(inter_load_max)
        data["paral_load_avg"].append(paral_load_avg)
        data["paral_load_max"].append(paral_load_max)
        data["paral_bn_avg"].append(paral_bn_avg)
        data["workload_opt_ratio"].append(workload_optimization_ratio(paral_bn_avg))
        data["workloads"] = workloads
        self.pn_rt_tor[pn][rt] = data
        if self.rt_pn_tor.get(rt, None) is None:
            self.rt_pn_tor[rt] = {}
        self.rt_pn_tor[rt][pn] = data

    def read_aor(self, filepath: str, chain_num: int, xtxratio: float):
        item = json.load(open(filepath, "r"))
        pn = item["para_num"]
        assert pn == chain_num, f"pn({pn}) != chainnum({chain_num})"
        rt = item["xtx_ratio"]
        assert rt == xtxratio, f"rt({rt}) != xtxratio({xtxratio})"
        interalltxs = item["interalltxs"]
        interdur = item.get("interdur", 0)  # 中继链上的全部处理时间
        tps = item["tps"]
        latency_avg = item["latency_avg"]
        ts_src_avg = item["ts_src_avg"]
        ts_rly01_avg = item["ts_rly01_avg"]
        ts_inter_avg = item["ts_inter_avg"]
        ts_rly02_avg = item["ts_rly02_avg"]
        ts_dst_avg = item["ts_dst_avg"]
        workload_file = item["workload_file"]
        workloads = json.load(open(workload_file, "r"))

        paral_loads_avg = []
        paral_loads_max = []
        paral_bns_avg = []
        for paral_chain, paral_loads in workloads.items():
            if paral_chain == "30000":
                continue
            paral_loads_avg.append(sum(paral_loads) / len(paral_loads))
            paral_loads_max.append(max(paral_loads))
            paral_bns_avg.append(len(paral_loads))

        paral_load_avg = sum(paral_loads_avg) / len(paral_loads_avg)
        paral_load_max = max(paral_loads_max)
        paral_bn_avg = sum(paral_bns_avg) / len(paral_bns_avg)

        inter_loads = workloads["30000"]
        inter_load_avg = sum(inter_loads) / len(inter_loads)
        inter_load_max = max(inter_loads)
        if self.pn_rt_aor.get(pn, None) is None:
            self.pn_rt_aor[pn] = {}
        if self.pn_rt_aor[pn].get(rt, None) is None:
            self.pn_rt_aor[pn][rt] = {
                "interalltxs": [],
                "interdur": [],
                "intertps": [],
                "tps": [],
                "latency_avg": [],
                "ts_src_avg": [],
                "ts_rly_avg": [],
                "ts_dst_avg": [],
                "inter_load_avg": [],
                "inter_load_max": [],
                "paral_load_avg": [],
                "paral_load_max": [],
                "paral_bn_avg": [],
                "workload_opt_ratio": [],
            }
        data = self.pn_rt_aor[pn][rt]
        data["interalltxs"].append(interalltxs)
        data["interdur"].append(interdur)
        data["intertps"].append(0 if int(interdur) == 0 else interalltxs / interdur)
        data["tps"].append(tps)
        data["latency_avg"].append(latency_avg)
        data["ts_src_avg"].append(ts_src_avg)
        data["ts_rly_avg"].append(ts_rly01_avg + ts_inter_avg + ts_rly02_avg)
        data["ts_dst_avg"].append(ts_dst_avg)
        data["inter_load_avg"].append(inter_load_avg)
        data["inter_load_max"].append(inter_load_max)
        data["paral_load_avg"].append(paral_load_avg)
        data["paral_load_max"].append(paral_load_max)
        data["paral_bn_avg"].append(paral_bn_avg)
        data["workload_opt_ratio"].append(workload_optimization_ratio(paral_bn_avg))
        data["workloads"] = workloads
        self.pn_rt_aor[pn][rt] = data
        if self.rt_pn_aor.get(rt, None) is None:
            self.rt_pn_aor[rt] = {}
        self.rt_pn_aor[rt][pn] = data

    def read_nor(self, filepath: str, chain_num: int, xtxratio: float):
        item = json.load(open(filepath, "r"))
        pn = item["para_num"]
        assert pn == chain_num, f"pn({pn}) != chainnum({chain_num})"
        rt = item["xtx_ratio"]
        assert rt == xtxratio, f"rt({rt}) != xtxratio({xtxratio})"
        interalltxs = item["interalltxs"]
        interdur = item.get("interdur", 0) 
        tps = item["tps"]
        latency_avg = item["latency_avg"]
        ts_src_avg = item["ts_src_avg"]
        ts_rly_avg = item["ts_rly_avg"]
        ts_dst_avg = item["ts_dst_avg"]
        workload_file = item["workload_file"]
        workloads = json.load(open(workload_file, "r"))

        paral_loads_avg = []
        paral_loads_max = []
        paral_bns_avg = []
        for paral_chain, paral_loads in workloads.items():
            # print(paral_chain)
            paral_loads_avg.append(sum(paral_loads) / len(paral_loads))
            paral_loads_max.append(max(paral_loads))
            paral_bns_avg.append(len(paral_loads))

        paral_bn_avg = sum(paral_bns_avg) / len(paral_bns_avg)
      
        paral_load_avg = sum(paral_loads_avg) / len(paral_loads_avg)
        paral_load_max = max(paral_loads_max)

        if self.pn_rt_nor.get(pn, None) is None:
            self.pn_rt_nor[pn] = {}
        if self.pn_rt_nor[pn].get(rt, None) is None:
            self.pn_rt_nor[pn][rt] = {
                "interalltxs": [],
                "interdur": [],
                "intertps": [],
                "tps": [],
                "latency_avg": [],
                "ts_src_avg": [],
                "ts_rly_avg": [],
                "ts_dst_avg": [],
                "paral_load_avg": [],
                "paral_load_max": [],
                "paral_bn_avg": [],
                "workload_opt_ratio": [],
            }
        data = self.pn_rt_nor[pn][rt]
        data["interalltxs"].append(interalltxs)
        data["interdur"].append(interdur)
        data["intertps"].append(0 if int(interdur) == 0 else interalltxs / interdur)
        data["tps"].append(tps)
        data["latency_avg"].append(latency_avg)
        data["ts_src_avg"].append(ts_src_avg)
        data["ts_rly_avg"].append(ts_rly_avg)
        data["ts_dst_avg"].append(ts_dst_avg)
        data["paral_load_avg"].append(paral_load_avg)
        data["paral_load_max"].append(paral_load_max)
        data["paral_bn_avg"].append(paral_bn_avg)
        data["workload_opt_ratio"].append(workload_optimization_ratio(paral_bn_avg))
        data["workloads"] = workloads
        self.pn_rt_nor[pn][rt] = data
        if self.rt_pn_nor.get(rt, None) is None:
            self.rt_pn_nor[rt] = {}
        self.rt_pn_nor[rt][pn] = data


def getxy(key: str, data: dict) -> [list, list]:
    ts_rly_avg = [(rt, y[key]) for rt, y in data.items()]
    ts_rly_avg = sorted(ts_rly_avg, key=lambda x: x[0])
    x = [item[0] for item in ts_rly_avg]
    y = [item[1] for item in ts_rly_avg]
    return x, y


def total_latency():
    data = Data()
    l = len(data.pn_rt_tor)
    lsqr = math.sqrt(l)
    ncol = math.floor(lsqr)
    nrow = math.ceil(lsqr)
    index = 0
    fig = plt.figure(figsize=(ncol * 3, nrow * 3))
    fig.suptitle("total_latency", fontsize=16)
    fig.tight_layout()
    plt.subplots_adjust(
        left=None, bottom=None, right=None, top=None, wspace=0.3, hspace=0.5
    )
    for pn, value in sorted(data.pn_rt_tor.items(), key=lambda x: x[0]):
        x, y = getxy("latency_avg", data.pn_rt_tor.get(pn, {}))
        x1, y1 = getxy("latency_avg", data.pn_rt_aor.get(pn, {}))
        x2, y2 = getxy("latency_avg", data.pn_rt_nor.get(pn, {}))
        index += 1
        print(nrow, ncol, index)
        ax = plt.subplot(
            nrow,
            ncol,
            index,
        )
        ax.set_title(f"pn={pn}")
        ax.set_xlabel("ratio")
        ax.set_ylabel("latency(sec)")
        # ax.set_ylim(ymin=0, ymax=250)
        ax.plot(x, y, label="ToR", marker="D")
        ax.plot(x1, y1, label="AoR", marker="s")
        ax.plot(x2, y2, label="NoR", marker="^")
        ax.legend()
    # lines, labels = fig.axes[-1].get_legend_handles_labels()
    # fig.legend(lines, labels, loc="upper left")
    fig.savefig(output_path("output_total_latency.jpg"))


def total_latency_reverse():
    data = Data()
    l = len(data.rt_pn_tor)
    lsqr = math.sqrt(l)
    ncol = math.floor(lsqr)
    nrow = math.ceil(lsqr)
    index = 0
    fig = plt.figure(figsize=(ncol * 3, nrow * 3))
    fig.suptitle("total_latency", fontsize=16)
    fig.tight_layout()
    plt.subplots_adjust(
        left=None, bottom=None, right=None, top=None, wspace=0.3, hspace=0.5
    )
    for ratio, value in sorted(data.rt_pn_tor.items(), key=lambda x: x[0]):
        # Change as cross-chain transactions ratio varies
        x, y = getxy("latency_avg", data.rt_pn_tor.get(ratio, {}))
        x1, y1 = getxy("latency_avg", data.rt_pn_aor.get(ratio, {}))
        x2, y2 = getxy("latency_avg", data.rt_pn_nor.get(ratio, {}))
        index += 1
        print(nrow, ncol, index)
        ax = plt.subplot(
            nrow,
            ncol,
            index,
        )
        ax.set_title(f"ratio={ratio}")
        ax.set_xlabel("pn")
        ax.set_ylabel("latency(sec)")
        ax.set_ylim(ymin=0, ymax=250)
        ax.plot(x, y, label="ToR", marker="D")
        ax.plot(x1, y1, label="AoR", marker="s")
        ax.plot(x2, y2, label="NoR", marker="^")
        ax.legend()
      
    # lines, labels = fig.axes[-1].get_legend_handles_labels()
    # fig.legend(lines, labels, loc="upper left")
    fig.savefig(output_path("output_total_latency_reverse.jpg"))


def rly_latency():
    data = Data()
    l = len(data.pn_rt_tor)
    lsqr = math.sqrt(l)
    ncol = math.floor(lsqr)
    nrow = math.ceil(lsqr)
    index = 0
    fig = plt.figure(figsize=(ncol * 3, nrow * 3))
    fig.suptitle("rly latency avg", fontsize=16)
    fig.tight_layout()
    plt.subplots_adjust(
        left=None, bottom=None, right=None, top=None, wspace=0.3, hspace=0.5
    )
    for pn, value in sorted(data.pn_rt_tor.items(), key=lambda x: x[0]):
        # Change as cross-chain transactions ratio varies
        x, y = getxy("ts_rly_avg", data.pn_rt_tor.get(pn, {}))
        x1, y1 = getxy("ts_rly_avg", data.pn_rt_aor.get(pn, {}))
        x2, y2 = getxy("ts_rly_avg", data.pn_rt_nor.get(pn, {}))
        index += 1
        ax = plt.subplot(
            nrow,
            ncol,
            index,
        )
        ax.set_title(f"pn={pn}")
        ax.set_xlabel("ratio")
        ax.set_ylabel("latency(sec)")
        # ax.set_ylim(ymin=0, ymax=230)
        ax.plot(x, y, label="ToR", marker="D")
        ax.plot(x1, y1, label="AoR", marker="s")
        ax.plot(x2, y2, label="NoR", marker="^")
        ax.legend()
    # lines, labels = fig.axes[-1].get_legend_handles_labels()
    # fig.legend(lines, labels, loc="center left")
    fig.savefig(output_path("output_rly_latency.jpg"))


def inter_duration():
    data = Data()
    l = len(data.pn_rt_tor)
    lsqr = math.sqrt(l)
    ncol = math.floor(lsqr)
    nrow = math.ceil(lsqr)
    index = 0
    fig = plt.figure(figsize=(ncol * 3, nrow * 3))
    fig.suptitle("inter total duration", fontsize=16)
    fig.tight_layout()
    plt.subplots_adjust(
        left=None, bottom=None, right=None, top=None, wspace=0.3, hspace=0.5
    )
    for pn, value in sorted(data.pn_rt_tor.items(), key=lambda x: x[0]):
        # Change as cross-chain transactions ratio varies
        x, y = getxy("interdur", data.pn_rt_tor.get(pn, {}))
        x1, y1 = getxy("interdur", data.pn_rt_aor.get(pn, {}))
        # x2, y2 = getxy("interdur", data.pn_rt_nor[pn])
        index += 1
        ax = plt.subplot(
            nrow,
            ncol,
            index,
        )
        ax.set_title(f"pn={pn}")
        ax.set_xlabel("ratio")
        ax.set_ylabel("latency(sec)")
        ax.set_ylim(ymin=0, ymax=250)
        ax.plot(x, y, label="ToR", marker="D")
        ax.plot(x1, y1, label="AoR", marker="s")
        # ax.plot(x2, y2, label="NoR")
        ax.legend()
    # lines, labels = fig.axes[-1].get_legend_handles_labels()
    # fig.legend(lines, labels, loc="center left")
    fig.savefig(output_path("output_inter_duration.jpg"))


def tps():
    data = Data()
    l = len(data.pn_rt_tor)
    lsqr = math.sqrt(l)
    ncol = math.floor(lsqr)
    nrow = math.ceil(lsqr)
    index = 0
    fig = plt.figure(figsize=(ncol * 3, nrow * 3))
    fig.suptitle("TPS", fontsize=16)
    fig.tight_layout()
    plt.subplots_adjust(
        left=None, bottom=None, right=None, top=None, wspace=0.5, hspace=0.5
    )
    for pn, value in sorted(data.pn_rt_tor.items(), key=lambda x: x[0]):
        # Change as cross-chain transactions ratio varies
        x, y = getxy("tps", data.pn_rt_tor.get(pn, {}))
        x1, y1 = getxy("tps", data.pn_rt_aor.get(pn, {}))
        x2, y2 = getxy("tps", data.pn_rt_nor.get(pn, {}))
        index += 1
        ax = plt.subplot(
            nrow,
            ncol,
            index,
        )
        ax.set_title(f"pn={pn}")
        ax.set_xlabel("ratio")
        ax.set_ylabel("TPS")
        # ax.set_ylim(ymin=0, ymax=1200)
        ax.plot(x, y, label="ToR", marker="D")
        ax.plot(x1, y1, label="AoR", marker="s")
        ax.plot(x2, y2, label="NoR", marker="^")
        ax.legend()
    plt.legend()
    # lines, labels = fig.axes[-1].get_legend_handles_labels()
    # fig.legend(lines, labels, loc="center left")
    fig.savefig(output_path("output_tps.jpg"))


def tps_reverse():
    data = Data()
    l = len(data.rt_pn_tor)
    lsqr = math.sqrt(l)
    ncol = math.floor(lsqr)
    nrow = math.ceil(lsqr)
    index = 0
    fig = plt.figure(figsize=(ncol * 3, nrow * 3))
    fig.suptitle("TPS", fontsize=16)
    fig.tight_layout()
    plt.subplots_adjust(
        left=None, bottom=None, right=None, top=None, wspace=0.3, hspace=0.5
    )
    for ratio, value in sorted(data.rt_pn_tor.items(), key=lambda x: x[0]):
        # Change as cross-chain transactions ratio varies
        x, y = getxy("tps", data.rt_pn_tor.get(ratio, {}))
        x1, y1 = getxy("tps", data.rt_pn_aor.get(ratio, {}))
        x2, y2 = getxy("tps", data.rt_pn_nor.get(ratio, {}))
        index += 1
        ax = plt.subplot(
            nrow,
            ncol,
            index,
        )
        ax.set_title(f"ratio={ratio}")
        ax.set_xlabel("pn")
        ax.set_ylabel("TPS")
        # ax.set_ylim(ymin=10, ymax=500)
        ax.plot(x, y, label="ToR", marker="D")
        ax.plot(x1, y1, label="AoR", marker="s")
        ax.plot(x2, y2, label="NoR", marker="^")
        ax.legend()
        
    plt.legend()
    fig.savefig(output_path("output_tps_reverse.jpg"))


def inter_load_avg_reverse():
    data = Data()
    l = len(data.rt_pn_tor)
    lsqr = math.sqrt(l)
    ncol = math.floor(lsqr)
    nrow = math.ceil(lsqr)
    index = 0
    fig = plt.figure(figsize=(ncol * 4, nrow * 4))
    # fig = plt.figure()
    fig.suptitle("workload average on relaychain", fontsize=16)
    fig.tight_layout()
    plt.subplots_adjust(
        left=None, bottom=None, right=None, top=None, wspace=0.3, hspace=0.3
    )

    total_width, n = 10, 2
    width = total_width / n
    width = width / 3 * 2
    for ratio, value in sorted(data.rt_pn_tor.items(), key=lambda x: x[0]):
        # Change as cross-chain transactions ratio varies
        x, y = getxy("inter_load_avg", data.rt_pn_tor.get(ratio, {}))
        y = [math.log(x, 2) for x in y]
        x1, y1 = getxy("inter_load_avg", data.rt_pn_aor.get(ratio, {}))
        y1 = [math.log(x, 2) for x in y1]

        xx, yy = getxy("inter_load_max", data.rt_pn_tor.get(ratio, {}))
        yy = [math.log(x, 2) for x in yy]
        xx1, yy1 = getxy("inter_load_max", data.rt_pn_aor.get(ratio, {}))
        yy1 = [math.log(x, 2) for x in yy1]

        index += 1
        ax = plt.subplot(
            nrow,
            ncol,
            index,
        )
        ax.set_title(f"ratio={ratio}")
        ax.set_xlabel("pn")
        ax.set_ylabel("tx")
        # ax.set_ylim(ymin=0, ymax=160)
        ax.plot(x, y, label="ToR-avg", marker="D", markersize=4)
        ax.plot(x1, y1, label="AoR-avg", marker="s", markersize=4)
        ax.legend()
        ax.bar(
            [i - width / 2 for i in xx],
            yy,
            width=width,
            label="ToR-max",
            color="white",
            edgecolor="blue",
            hatch="....",
        )
        ax.bar(
            [i + width / 2 for i in xx1],
            yy1,
            width=width,
            label="AoR-max",
            color="white",
            edgecolor="orange",
            hatch="////",
        )
        # for a, b in zip(x, y):
        #     ax.text(a-width/2, b+1, f"{b:.2f}", ha='center', va='bottom', fontsize=8)
        # for a, b in zip(x1, y1):
        #     ax.text(a+width/2, b+1, f"{b:.2f}", ha='center', va='bottom', fontsize=8)
    fig.savefig(output_path("output_inter_load_avg_reverse.jpg"))


def paral_load_avg_reverse():
    data = Data()
    l = len(data.rt_pn_tor)
    lsqr = math.sqrt(l)
    ncol = math.floor(lsqr)
    nrow = math.ceil(lsqr)
    index = 0
    fig = plt.figure(figsize=(ncol * 3, nrow * 3))
    # fig = plt.figure()
    fig.suptitle("load average on parallel chain (increase pn)", fontsize=16)
    fig.tight_layout()
    plt.subplots_adjust(
        left=None, bottom=None, right=None, top=None, wspace=None, hspace=0.5
    )

    total_width, n = 10, 3
    width = total_width / n
    width = width / 4 * 3
    for ratio, value in sorted(data.rt_pn_tor.items(), key=lambda x: x[0]):
        # Change as cross-chain transactions ratio varies
        x, y = getxy("paral_load_avg", data.rt_pn_tor.get(ratio, {}))
        y = [math.log(x, 2) for x in y]
        x1, y1 = getxy("paral_load_avg", data.rt_pn_aor.get(ratio, {}))
        y1 = [math.log(x, 2) for x in y1]
        x2, y2 = getxy("paral_load_avg", data.rt_pn_nor.get(ratio, {}))
        y2 = [math.log(x, 2) for x in y2]

        xx, yy = getxy("paral_load_max", data.rt_pn_tor.get(ratio, {}))
        yy = [math.log(x, 2) for x in yy]
        xx1, yy1 = getxy("paral_load_max", data.rt_pn_aor.get(ratio, {}))
        yy1 = [math.log(x, 2) for x in yy1]
        xx2, yy2 = getxy("paral_load_max", data.rt_pn_nor.get(ratio, {}))
        yy2 = [math.log(x, 2) for x in yy2]

        index += 1
        ax = plt.subplot(
            nrow,
            ncol,
            index,
        )
        ax.set_title(f"ratio={ratio}")
        ax.set_xlabel("pn")
        ax.set_ylabel("tx")
        # ax.set_ylim(ymin=0, ymax=160)
        ax.plot(x, y, label="ToR-avg", marker="D", markersize=4)
        ax.plot(x1, y1, label="AoR-avg", marker="s", markersize=4)
        ax.plot(x2, y2, label="NoR-avg", marker="^", markersize=4)
        ax.legend()
        ax.bar(
            [i - width for i in xx],
            yy,
            width=width,
            label="ToR-max",
            color="white",
            edgecolor="blue",
            hatch="....",
        )
        ax.bar(
            [i for i in xx1],
            yy1,
            width=width,
            label="AoR-max",
            color="white",
            edgecolor="orange",
            hatch="////",
        )
        ax.bar(
            [i + width for i in xx2],
            yy2,
            width=width,
            label="NoR-max",
            color="white",
            edgecolor="green",
            hatch="////",
        )
        # for a, b in zip(x, y):
        #     ax.text(a-width/2, b+1, f"{b:.2f}", ha='center', va='bottom', fontsize=8)
        # for a, b in zip(x1, y1):
        #     ax.text(a+width/2, b+1, f"{b:.2f}", ha='center', va='bottom', fontsize=8)
    fig.savefig(output_path("output_paral_load_avg_reverse.jpg"))


def inter_load_delta():
    def normalization(data: list):
        maxv = max(data)
        minv = min(data)
        _range = maxv - minv
        return [(x - minv) / _range for x in data]

    data = Data()
    ncol = 1
    nrow = 1
    index = 0
    fig = plt.figure(figsize=(9, 9))
    # fig = plt.figure()
    # fig.suptitle("load of relaychain", fontsize=16)
    fig.tight_layout()
    plt.subplots_adjust(
        left=None, bottom=None, right=None, top=None, wspace=None, hspace=0.5
    )

    index += 1
    ax = plt.subplot(
        nrow,
        ncol,
        index,
    )
    pns = set()
    markers = ["o", "^", "*", "s", "D", "p"]
    marker_id = 0
    pns = {x[0] for x in data.rt_pn_tor[list(data.rt_pn_tor.items())[0][0]].items()}
    pns = normalization(sorted(list(pns)))
    rts = set()
    ax.set_xlim(0, 1)
    ax.set_ylim(0, 1)
    # ax.set_xlabel("ratio")
    for rt, value in data.rt_pn_tor.items():
        # Change as cross-chain transactions ratio varies
        rts.add(rt)
        x, y = getxy("inter_load_avg", data.rt_pn_tor[rt])
        x = normalization(x)
        y = normalization(y)
        marker_id += 1
        ax.plot(x, y, label=f"ratio-{rt}", marker=markers[marker_id], linestyle="-")

    ax.plot(x, pns, label="pn")
    for a, b in zip(x, pns):
        ax.axhline(y=b, xmax=a, xmin=0, linestyle="dotted")
        ax.axvline(x=a, ymax=b, ymin=0, linestyle="dotted")
    ax.legend()

    fig.savefig(output_path("output_inter_load_delta.jpg"))


def inter_totaltxs():
    data = Data()
    ncol = 3
    nrow = len(data.pn_rt_tor) // ncol
    index = 0
    fig = plt.figure(figsize=(13, 6))
    # fig = plt.figure()
    fig.suptitle("total txs on relaychain", fontsize=16)
    fig.tight_layout()
    plt.subplots_adjust(
        left=None, bottom=None, right=None, top=None, wspace=None, hspace=0.5
    )

    total_width, n = 0.2, 2
    width = total_width / n
    width = width / 3 * 2
    for pn, value in data.pn_rt_tor.items():
        # Change as cross-chain transactions ratio varies
        x, y = getxy("interalltxs", data.pn_rt_tor[pn])
        # y = [math.log(x, 2) for x in y]
        x1, y1 = getxy("interalltxs", data.pn_rt_aor[pn])
        # y1 = [math.log(x, 2) for x in y1]
        index += 1
        ax = plt.subplot(
            nrow,
            ncol,
            index,
        )
        ax.set_title(f"pn={pn}")
        ax.set_xlabel("ratio")
        ax.set_ylabel("tx/s")
        # ax.set_ylim(ymin=0, ymax=160)
        ax.plot(x, y, label="ToR", marker="D", markersize=4)
        ax.plot(x1, y1, label="AoR", marker="s", markersize=4)
        ax.legend()
        ax.bar(
            [i - width / 2 for i in x],
            y,
            width=width,
            label="ToR",
            color="white",
            edgecolor="blue",
            hatch="....",
        )
        ax.bar(
            [i + width / 2 for i in x1],
            y1,
            width=width,
            label="AoR",
            color="white",
            edgecolor="orange",
            hatch="////",
        )
        for a, b in zip(x, y):
            ax.text(
                a - width / 2, b + 1, f"{b:.2f}", ha="center", va="bottom", fontsize=8
            )
        for a, b in zip(x1, y1):
            ax.text(
                a + width / 2, b + 1, f"{b:.2f}", ha="center", va="bottom", fontsize=8
            )
    fig.savefig(output_path("output_inter_totaltxs.jpg"))


def inter_load_max():
    data = Data()
    ncol = 3
    nrow = len(data.pn_rt_tor) // ncol
    index = 0
    fig = plt.figure(figsize=(13, 6))
    # fig = plt.figure()
    fig.suptitle("max load on relaychain", fontsize=16)
    fig.tight_layout()
    plt.subplots_adjust(
        left=None, bottom=None, right=None, top=None, wspace=None, hspace=0.5
    )

    total_width, n = 0.2, 2
    width = total_width / n
    width = width / 3 * 2
    for pn, value in data.pn_rt_tor.items():
        # Change as cross-chain transactions ratio varies
        x, y = getxy("inter_load_max", data.pn_rt_tor[pn])
        y = [math.log(x, 2) for x in y]
        x1, y1 = getxy("inter_load_max", data.pn_rt_aor[pn])
        y1 = [math.log(x, 2) for x in y1]
        index += 1
        ax = plt.subplot(
            nrow,
            ncol,
            index,
        )
        ax.set_title(f"pn={pn}")
        ax.set_xlabel("ratio")
        ax.set_ylabel("tx")
        # ax.set_ylim(ymin=0, ymax=160)
        ax.plot(x, y, label="ToR", marker="D", markersize=4)
        ax.plot(x1, y1, label="AoR", marker="s", markersize=4)
        ax.legend()
        ax.bar(
            [i - width / 2 for i in x],
            y,
            width=width,
            label="ToR",
            color="white",
            edgecolor="blue",
            hatch="....",
        )
        ax.bar(
            [i + width / 2 for i in x1],
            y1,
            width=width,
            label="AoR",
            color="white",
            edgecolor="orange",
            hatch="////",
        )
        for a, b in zip(x, y):
            ax.text(
                a - width / 2, b + 1, f"{b:.2f}", ha="center", va="bottom", fontsize=8
            )
        for a, b in zip(x1, y1):
            ax.text(
                a + width / 2, b + 1, f"{b:.2f}", ha="center", va="bottom", fontsize=8
            )
    fig.savefig(output_path("output_inter_load_max.jpg"))


def inter_load_avg():
    data = Data()
    l = len(data.pn_rt_tor)
    lsqr = math.sqrt(l)
    ncol = math.floor(lsqr)
    nrow = math.ceil(lsqr)
    index = 0
    fig = plt.figure(figsize=(ncol * 3, nrow * 3))
    # fig = plt.figure()
    fig.suptitle("average load on relaychain (increase xtxratio)", fontsize=16)
    fig.tight_layout()
    plt.subplots_adjust(
        left=None, bottom=None, right=None, top=None, wspace=0.3, hspace=0.5
    )

    total_width, n = 0.2, 2
    width = total_width / n
    width = width / 3 * 2
    for pn, value in sorted(data.pn_rt_tor.items(), key=lambda x: x[0]):
        # Change as cross-chain transactions ratio varies
        x, y = getxy("inter_load_avg", data.pn_rt_tor.get(pn, {}))
        y = [math.log(x, 2) for x in y]
        x1, y1 = getxy("inter_load_avg", data.pn_rt_aor.get(pn, {}))
        y1 = [math.log(x, 2) for x in y1]

        xx, yy = getxy("inter_load_max", data.pn_rt_tor.get(pn, {}))
        yy = [math.log(x, 2) for x in yy]
        xx1, yy1 = getxy("inter_load_max", data.pn_rt_aor.get(pn, {}))
        yy1 = [math.log(x, 2) for x in yy1]

        index += 1
        ax = plt.subplot(
            nrow,
            ncol,
            index,
        )
        ax.set_title(f"pn={pn}")
        ax.set_xlabel("ratio")
        ax.set_ylabel("tx number")
        # ax.set_ylim(ymin=0, ymax=160)
        ax.plot(x, y, label="ToR-avg", marker="D", markersize=4)
        ax.plot(x1, y1, label="AoR-avg", marker="s", markersize=4)
        ax.bar(
            [i - width / 2 for i in xx],
            yy,
            width=width,
            label="ToR-max",
            color="white",
            edgecolor="blue",
            hatch="....",
        )
        ax.bar(
            [i + width / 2 for i in xx1],
            yy1,
            width=width,
            label="AoR-max",
            color="white",
            edgecolor="orange",
            hatch="////",
        )
        # ax.legend()
    #     for a, b in zip(x, y):
    #         ax.text(a-width/2, b+1, f"{b:.2f}", ha='center', va='bottom', fontsize=8)
    #     for a, b in zip(x1, y1):
    #         ax.text(a+width/2, b+1, f"{b:.2f}", ha='center', va='bottom', fontsize=8)
    lines, labels = fig.axes[-1].get_legend_handles_labels()
    fig.legend(lines, labels, loc="center left")
    fig.savefig(output_path("output_inter_load_avg.jpg"))


def paral_load_avg():
    data = Data()
    l = len(data.pn_rt_tor)
    lsqr = math.sqrt(l)
    ncol = math.floor(lsqr)
    nrow = math.ceil(lsqr)
    index = 0
    fig = plt.figure(figsize=(ncol * 3, nrow * 3))
    # fig = plt.figure()
    fig.suptitle("average load on parallel chain (increase xtxratio)", fontsize=16)
    fig.tight_layout()
    plt.subplots_adjust(
        left=None, bottom=None, right=None, top=None, wspace=0.3, hspace=0.5
    )

    total_width, n = 0.2, 3
    width = total_width / n
    width = width / 4 * 3
    for pn, value in sorted(data.pn_rt_tor.items(), key=lambda x: x[0]):
        # Change as cross-chain transactions ratio varies
        x, y = getxy("paral_load_avg", data.pn_rt_tor.get(pn, {}))
        y = [math.log(x, 2) for x in y]
        x1, y1 = getxy("paral_load_avg", data.pn_rt_aor.get(pn, {}))
        y1 = [math.log(x, 2) for x in y1]
        x2, y2 = getxy("paral_load_avg", data.pn_rt_nor.get(pn, {}))
        y2 = [math.log(x, 2) for x in y2]

        xx, yy = getxy("paral_load_max", data.pn_rt_tor.get(pn, {}))
        yy = [math.log(x, 2) for x in yy]
        xx1, yy1 = getxy("paral_load_max", data.pn_rt_aor.get(pn, {}))
        yy1 = [math.log(x, 2) for x in yy1]
        xx2, yy2 = getxy("paral_load_max", data.pn_rt_nor.get(pn, {}))
        yy2 = [math.log(x, 2) for x in yy2]

        index += 1
        ax = plt.subplot(
            nrow,
            ncol,
            index,
        )
        ax.set_title(f"pn={pn}")
        ax.set_xlabel("ratio")
        ax.set_ylabel("tx number")
        # ax.set_ylim(ymin=0, ymax=160)
        ax.plot(x, y, label="ToR-avg", marker="D", markersize=4)
        ax.plot(x1, y1, label="AoR-avg", marker="s", markersize=4)
        ax.plot(x2, y2, label="NoR-avg", marker="^", markersize=4)
        ax.bar(
            [i - width for i in xx],
            yy,
            width=width,
            label="ToR-max",
            color="white",
            edgecolor="blue",
            hatch="....",
        )
        ax.bar(
            [i for i in xx1],
            yy1,
            width=width,
            label="AoR-max",
            color="white",
            edgecolor="orange",
            hatch="////",
        )
        ax.bar(
            [i + width for i in xx2],
            yy2,
            width=width,
            label="NoR-max",
            color="white",
            edgecolor="green",
            hatch="////",
        )
        # ax.legend()
    #     for a, b in zip(x, y):
    #         ax.text(a-width/2, b+1, f"{b:.2f}", ha='center', va='bottom', fontsize=8)
    #     for a, b in zip(x1, y1):
    #         ax.text(a+width/2, b+1, f"{b:.2f}", ha='center', va='bottom', fontsize=8)
    lines, labels = fig.axes[-1].get_legend_handles_labels()
    fig.legend(lines, labels, loc="center left")
    fig.savefig(output_path("output_paral_load_avg.jpg"))


def inter_ratio():
    data = Data()
    ncol = 1
    nrow = 1
    index = 0
    fig = plt.figure(figsize=(9, 9))
    # fig = plt.figure()
    # fig.suptitle("all txs number on relaychain", fontsize=16)
    fig.tight_layout()
    plt.subplots_adjust(
        left=None, bottom=None, right=None, top=None, wspace=None, hspace=0.5
    )
    index += 1
    ax = plt.subplot(
        nrow,
        ncol,
        index,
    )
    # ax.set_title(f"reduction of relaychain's load", fontdict={'fontsize': 16})
    ax.set_xlabel("ratio")
    ax.set_ylabel("decrease ratio")
    ax.set_ylim(0.6, 1.0)
    markers = [
        "o",
        "^",
        "v",
        "1",
        "*",
        "s",
        "D",
        "p",
        "X",
        "x",
        "P",
        "o",
        "^",
        "v",
        "1",
        "*",
        "s",
        "D",
        "p",
        "X",
        "x",
        "P",
    ]
    marker_id = 0
    maxv = 0
    minv = 100
    sumv = []
    for pn, value in sorted(data.pn_rt_tor.items(), key=lambda x: x[0]):
        # Change as cross-chain transactions ratio varies
        x, y = getxy("inter_load_avg", data.pn_rt_tor.get(pn, {}))
        x1, y1 = getxy("inter_load_avg", data.pn_rt_aor.get(pn, {}))
        # x, y = getxy("intertps", data.pn_rt_tor[pn])
        # x1, y1 = getxy("intertps", data.pn_rt_aor[pn])
        a, b = x, [1 - p / p1 for (p, p1) in zip(y, y1)]
        bavg = sum(b) / len(b)
        diff2 = (sum((x - bavg) ** 2 for x in b) / len(b)) ** (1 / 2)
        print(f"diff2 of pn({pn}): {diff2}")
        # a, b = x, [1-math.log(p,2)/math.log(p1, 2) for (p, p1) in zip(y, y1)]
        maxv = max(maxv, max(b))
        minv = min(minv, min(b))
        sumv.extend(b)
        ax.plot(a, b, label=str(pn), marker=markers[marker_id], markersize=10)
        marker_id += 1
    ax.axhline(y=maxv, color="green", xmin=0, xmax=1.0, linewidth=1, linestyle="dashed")
    ax.text(0.3, maxv - 0.003, s=f"max={maxv:.2f}", fontsize=10, color="green")
    ax.axhline(y=minv, color="green", xmin=0, xmax=1.0, linewidth=1, linestyle="dashed")
    ax.text(0.3, minv + 0.003, s=f"min={minv:.2f}", fontsize=10, color="green")
    avgv = sum(sumv) / len(sumv)
    ax.axhline(y=avgv, color="red", xmin=0, xmax=1.0, linewidth=2, linestyle="dashed")
    ax.text(0.7, avgv - 0.003, s=f"avg={avgv:.2f}", fontsize=14, color="r")
    ax.legend()
    fig.savefig(output_path("output_inter_ratio.jpg"))


def inter_ratio_reverse():
    data = Data()
    ncol = 1
    nrow = 1
    index = 0
    fig = plt.figure(figsize=(9, 9))
    # fig = plt.figure()
    # fig.suptitle("all txs number on relaychain", fontsize=16)
    fig.tight_layout()
    plt.subplots_adjust(
        left=None, bottom=None, right=None, top=None, wspace=None, hspace=0.5
    )
    index += 1
    ax = plt.subplot(
        nrow,
        ncol,
        index,
    )
    # ax.set_title(f"reduction of relaychain's load", fontdict={'fontsize': 16})
    ax.set_xlabel("ratio")
    ax.set_ylabel("decrease ratio")
    ax.set_ylim(0.75, 1.0)
    markers = ["o", "^", "v", "1", "*", "s", "D", "p", "X", "x", "P"]
    marker_id = 0
    maxv = 0
    minv = 100
    sumv = []
    for ratio, value in sorted(data.rt_pn_tor.items(), key=lambda x: x[0]):
        # Change as cross-chain transactions ratio varies
        x, y = getxy("inter_load_avg", data.rt_pn_tor[ratio])
        x1, y1 = getxy("inter_load_avg", data.rt_pn_aor[ratio])
        # x, y = getxy("intertps", data.pn_rt_tor[pn])
        # x1, y1 = getxy("intertps", data.pn_rt_aor[pn])
        a, b = x, [1 - p / p1 for (p, p1) in zip(y, y1)]
        # a, b = x, [1-math.log(p,2)/math.log(p1, 2) for (p, p1) in zip(y, y1)]
        bavg = sum(b) / len(b)
        diff2 = (sum((x - bavg) ** 2 for x in b) / len(b)) ** (1 / 2)
        print(f"diff2 of ratio({ratio}): {diff2:.7f}")
        maxv = max(maxv, max(b))
        minv = min(minv, min(b))
        sumv.extend(b)
        ax.plot(a, b, label=str(ratio), marker=markers[marker_id], markersize=10)
        marker_id += 1
    ax.axhline(y=maxv, color="green", xmin=0, xmax=1.0, linewidth=1, linestyle="dashed")
    ax.text(5, maxv, s=f"max={maxv:.2f}", fontsize=10, color="green")
    ax.axhline(y=minv, color="green", xmin=0, xmax=1.0, linewidth=1, linestyle="dashed")
    ax.text(10, minv + 0.003, s=f"min={minv:.2f}", fontsize=10, color="green")
    avgv = sum(sumv) / len(sumv)
    ax.axhline(y=avgv, color="red", xmin=0, xmax=1.0, linewidth=2, linestyle="dashed")
    ax.text(30, avgv, s=f"avg={avgv:.2f}", fontsize=14, color="r")
    ax.legend()
    fig.savefig(output_path("output_inter_ratio_reverse.jpg"))


def inter_load_avg_simple():
    data = Data()
    l = len(data.pn_rt_tor)
    lsqr = math.sqrt(l)
    ncol = 2
    nrow = 1
    index = 0
    fig = plt.figure(figsize=(ncol * 3, nrow * 3))
    # fig = plt.figure()
    fig.suptitle("average load on relaychain (increase xtxratio)", fontsize=16)
    fig.tight_layout()
    plt.subplots_adjust(
        left=None, bottom=None, right=None, top=None, wspace=0.3, hspace=0.5
    )

    total_width, n = 0.2, 2
    width = total_width / n
    width = width / 3 * 2
    # pn=35, vary by xtxratio
    pn = 35
    x, y = getxy("inter_load_avg", data.pn_rt_tor.get(pn, {}))
    y = [math.log(x, 2) for x in y]
    x1, y1 = getxy("inter_load_avg", data.pn_rt_aor.get(pn, {}))
    y1 = [math.log(x, 2) for x in y1]
    xx, yy = getxy("inter_load_max", data.pn_rt_tor.get(pn, {}))
    yy = [math.log(x, 2) for x in yy]
    xx1, yy1 = getxy("inter_load_max", data.pn_rt_aor.get(pn, {}))
    yy1 = [math.log(x, 2) for x in yy1]
    index += 1
    ax = plt.subplot(
        nrow,
        ncol,
        index,
    )
    ax.set_title(f"pn={pn}")
    ax.set_xlabel("ratio")
    ax.set_ylabel("tx number")
    # ax.set_ylim(ymin=0, ymax=160)
    ax.plot(x, y, label="ToR-avg", marker="D", markersize=4)
    ax.plot(x1, y1, label="AoR-avg", marker="s", markersize=4)
    ax.bar(
        [i - width / 2 for i in xx],
        yy,
        width=width,
        label="ToR-max",
        color="white",
        edgecolor="blue",
        hatch="....",
    )
    ax.bar(
        [i + width / 2 for i in xx1],
        yy1,
        width=width,
        label="AoR-max",
        color="white",
        edgecolor="orange",
        hatch="////",
    )
    ax.legend()

    total_width, n = 10, 2
    width = total_width / n
    width = width / 3 * 2
    # xtxratio=0.8, vary by pn
    ratio = 0.8
    x, y = getxy("inter_load_avg", data.rt_pn_tor[ratio])
    y = [math.log(x, 2) for x in y]
    x1, y1 = getxy("inter_load_avg", data.rt_pn_aor[ratio])
    y1 = [math.log(x, 2) for x in y1]
    xx, yy = getxy("inter_load_max", data.rt_pn_tor[ratio])
    yy = [math.log(x, 2) for x in yy]
    xx1, yy1 = getxy("inter_load_max", data.rt_pn_aor[ratio])
    yy1 = [math.log(x, 2) for x in yy1]
    index += 1
    ax = plt.subplot(
        nrow,
        ncol,
        index,
    )
    ax.set_title(f"ratio={ratio}")
    ax.set_xlabel("pn")
    ax.set_ylabel("tx number")
    # ax.set_ylim(ymin=0, ymax=160)
    ax.plot(x, y, label="ToR-avg", marker="D", markersize=4)
    ax.plot(x1, y1, label="AoR-avg", marker="s", markersize=4)
    ax.bar(
        [i - width / 2 for i in xx],
        yy,
        width=width,
        label="ToR-max",
        color="white",
        edgecolor="blue",
        hatch="....",
    )
    ax.bar(
        [i + width / 2 for i in xx1],
        yy1,
        width=width,
        label="AoR-max",
        color="white",
        edgecolor="orange",
        hatch="////",
    )
    ax.legend()

    #     for a, b in zip(x, y):
    #         ax.text(a-width/2, b+1, f"{b:.2f}", ha='center', va='bottom', fontsize=8)
    #     for a, b in zip(x1, y1):
    #         ax.text(a+width/2, b+1, f"{b:.2f}", ha='center', va='bottom', fontsize=8)
    # lines, labels = fig.axes[-1].get_legend_handles_labels()
    # fig.legend(lines, labels, loc = 'center left')
    fig.savefig(output_path("output_inter_load_avg_simple.jpg"))


def total_latency_simple():
    data = Data()
    ncol = 2
    nrow = 1
    index = 0
    fig = plt.figure(figsize=(13, 6))
    fig.suptitle("total_latency", fontsize=16)
    fig.tight_layout()
    plt.subplots_adjust(
        left=None, bottom=None, right=None, top=None, wspace=None, hspace=0.5
    )

    # pn=35, vary by xtxratio
    pn = 35
    x, y = getxy("latency_avg", data.pn_rt_tor[pn])
    x1, y1 = getxy("latency_avg", data.pn_rt_aor[pn])
    x2, y2 = getxy("latency_avg", data.pn_rt_nor[pn])
    index += 1
    ax = plt.subplot(
        nrow,
        ncol,
        index,
    )
    ax.set_title(f"pn={pn}")
    ax.set_xlabel("ratio")
    ax.set_ylabel("latency(sec)")
    # ax.set_ylim(ymin=0, ymax=140)
    ax.plot(x, y, label="ToR", marker="D")
    ax.plot(x1, y1, label="AoR", marker="s")
    ax.plot(x2, y2, label="NoR", marker="^")
    ax.legend()

    # xtxratio=0.6, vary by pn
    ratio = 0.4
    x, y = getxy("latency_avg", data.rt_pn_tor[ratio])
    x1, y1 = getxy("latency_avg", data.rt_pn_aor[ratio])
    x2, y2 = getxy("latency_avg", data.rt_pn_nor[ratio])
    index += 1
    ax = plt.subplot(
        nrow,
        ncol,
        index,
    )
    ax.set_title(f"ratio={ratio}")
    ax.set_xlabel("pn")
    ax.set_ylabel("latency(sec)")
    # ax.set_ylim(ymin=0, ymax=140)
    ax.plot(x, y, label="ToR", marker="D")
    ax.plot(x1, y1, label="AoR", marker="s")
    ax.plot(x2, y2, label="NoR", marker="^")
    ax.legend()

    fig.savefig(output_path("output_total_latency_simple.jpg"))


def paral_workload_change():
    datapath_load = "./locals/output/workloads"
    filenameToR = [
        "ToR-30-500-20.json",
        "ToR-70-500-20.json",
        "ToR-100-500-20.json",
        "ToR-140-500-20.json",
    ]
    filenameAoR = [
        "AoR-30-500-20.json",
        "AoR-70-500-20.json",
        "AoR-100-500-20.json",
        "AoR-140-500-20.json",
    ]
    filenameNoR = [
        "NoR-30-500-20.json",
        "NoR-70-500-20.json",
        "NoR-100-500-20.json",
        "NoR-140-500-20.json",
    ]
    parachainnum = [30, 70, 100, 140]
    ncol = 2
    nrow = 2
    index = 0

    filepathToR = []
    filepathAoR = []
    filepathNoR = []
    itemToR = []
    itemAoR = []
    itemNoR = []
    fig = plt.figure(figsize=(10, 10))
    fig.suptitle("workload change on parallel chain", fontsize=16)
    fig.tight_layout()
    plt.subplots_adjust(
        left=None, bottom=None, right=None, top=None, wspace=0.3, hspace=0.3
    )
    for i in range(0, 4, 1):
        filepathToR.append(os.path.join(datapath_load, filenameToR[i]))
        itemToR.append(json.load(open(filepathToR[i], "r")))

        filepathAoR.append(os.path.join(datapath_load, filenameAoR[i]))
        itemAoR.append(json.load(open(filepathAoR[i], "r")))

        filepathNoR.append(os.path.join(datapath_load, filenameNoR[i]))
        itemNoR.append(json.load(open(filepathNoR[i], "r")))

        strchainid = "0"
        xToR = list(range(1, len(itemToR[i][strchainid]) + 1, 1))
        xAoR = list(range(1, len(itemAoR[i][strchainid]) + 1, 1))
        xNoR = list(range(1, len(itemNoR[i][strchainid]) + 1, 1))
        yToR = itemToR[i][strchainid]
        yAoR = itemAoR[i][strchainid]
        yNoR = itemNoR[i][strchainid]

        index += 1
        ax = plt.subplot(
            nrow,
            ncol,
            index,
        )
        ax.set_title(f"pn={parachainnum[i]}")
        ax.set_xlabel("time")
        ax.set_ylabel("workload")
        # ax.set_ylim(ymin=0, ymax=160)
        ax.plot(xToR, yToR, label="ToR", marker="D", markersize=4)
        ax.plot(xAoR, yAoR, label="AoR", marker="s", markersize=4)
        ax.plot(xNoR, yNoR, label="NoR", marker="^", markersize=4)

        ax.legend(loc="upper right", bbox_to_anchor=(1, 1), fontsize="small")

        if parachainnum[i] == 30:
            continue

        axins = ax.inset_axes((0.58, 0.15, 0.4, 0.3))
        axins.plot(
            xToR,
            yToR,
            color="#055DF3",
            alpha=0.8,
            marker="D",
            markersize=2,
            label="ToR",
        )
        axins.plot(
            xAoR,
            yAoR,
            color="#E67E22",
            alpha=0.8,
            marker="s",
            markersize=2,
            label="AoR",
        )

        xlim0 = 10
        xlim1 = 30
        ylim0 = 0 - 10
        ylim1 = 100
        axins.set_xlim(xlim0, xlim1)
        axins.set_ylim(ylim0, ylim1)

        tx0 = xlim0
        tx1 = xlim1
        ty0 = ylim0 - 20
        ty1 = ylim1
        sx = [tx0, tx1, tx1, tx0, tx0]
        sy = [ty0, ty0, ty1, ty1, ty0]
        ax.plot(sx, sy, "black")

        xy = (xlim1, ylim1)
        xy2 = (xlim0, ylim1)
        con = ConnectionPatch(
            xyA=xy2,
            xyB=xy,
            coordsA="data",
            coordsB="data",
            axesA=axins,
            axesB=ax,
            linestyle="dotted",
        )
        axins.add_artist(con)

        xy = (xlim1, ylim0 - 20) 
        xy2 = (xlim0, ylim0) 
        con = ConnectionPatch(
            xyA=xy2,
            xyB=xy,
            coordsA="data",
            coordsB="data",
            axesA=axins,
            axesB=ax,
            linestyle="dotted",
        )
        axins.add_artist(con)

    fig.savefig(output_path("output_paral_workload_change.jpg"))


def essay_paral_workload_change():
    datapath_load = "./locals/output/workloads"
    filenameToR = [
        "ToR-30-500-20.json",
        "ToR-70-500-20.json",
        "ToR-100-500-20.json",
        "ToR-140-500-20.json",
    ]
    filenameAoR = [
        "AoR-30-500-20.json",
        "AoR-70-500-20.json",
        "AoR-100-500-20.json",
        "AoR-140-500-20.json",
    ]
    filenameNoR = [
        "NoR-30-500-20.json",
        "NoR-70-500-20.json",
        "NoR-100-500-20.json",
        "NoR-140-500-20.json",
    ]
    parachainnum = [10, 60, 120, 180]
    ncol = 2
    nrow = 2
    index = 0

    filepathToR = []
    filepathAoR = []
    filepathNoR = []
    itemToR = []
    itemAoR = []
    itemNoR = []

    for i in range(0, 4, 1):
        fig = plt.figure(figsize=(9, 7))
        plt.rcParams["font.weight"] = "bold"
        plt.rcParams["axes.labelweight"] = "bold"
        SMALL_SIZE = 20
        MEDIUM_SIZE = 26
        plt.rc("font", size=MEDIUM_SIZE)  # controls default text sizes
        plt.rc("axes", labelsize=MEDIUM_SIZE)  # fontsize of the x and y labels
        plt.rc("xtick", labelsize=SMALL_SIZE)  # fontsize of the tick labels
        plt.rc("ytick", labelsize=SMALL_SIZE)  # fontsize of the tick labels
        plt.rc("legend", fontsize=SMALL_SIZE)  # legend fontsize
        plt.rc("figure", titlesize=MEDIUM_SIZE)  # fontsize of the figure title
        # fig.suptitle("total_latency", fontsize=16)
        fig.tight_layout()
        plt.subplots_adjust(
            left=None, bottom=None, right=None, top=None, wspace=0.1, hspace=0.1
        )
        filepathToR.append(os.path.join(datapath_load, filenameToR[i]))
        itemToR.append(json.load(open(filepathToR[i], "r")))

        filepathAoR.append(os.path.join(datapath_load, filenameAoR[i]))
        itemAoR.append(json.load(open(filepathAoR[i], "r")))

        filepathNoR.append(os.path.join(datapath_load, filenameNoR[i]))
        itemNoR.append(json.load(open(filepathNoR[i], "r")))

        strchainid = "0"
        xToR = list(range(1, len(itemToR[i][strchainid]) + 1, 1))
        xAoR = list(range(1, len(itemAoR[i][strchainid]) + 1, 1))
        xNoR = list(range(1, len(itemNoR[i][strchainid]) + 1, 1))
        yToR = itemToR[i][strchainid]
        yAoR = itemAoR[i][strchainid]
        yNoR = itemNoR[i][strchainid]

        index += 1
        ax = plt.subplot(
            1,1,1
        )
        
        ax.set_title(f"pn={parachainnum[i]}")
        ax.set_xlabel("time")
        if index in [1,2]:
            ax.set_ylabel("workload")
        elif index ==3 :
            ax.set_ylabel("workload",labelpad=-10)
        else:
            yticks = [1000,2000,3000,4000,5000]
            yticklabels = ['{}k'.format(ytick) for ytick in [1,2,3,4,5]]
            ax.set_yticks(yticks)
            ax.set_yticklabels(yticklabels)
            ax.set_ylabel("workload")
        ax.plot(xToR, yToR, label="ToR", marker="D",  linewidth=4,
                mew=10,
                ms=3)
        ax.plot(xAoR, yAoR, label="AoR", marker="s",  linewidth=4,
                mew=10,
                ms=3)
        ax.plot(xNoR, yNoR, label="NoR", marker="^",  linewidth=4,
                mew=10,
                ms=3)

        ax.legend(loc="upper right", bbox_to_anchor=(1, 1), fontsize="medium")

        if parachainnum[i] == 10:
            fig.savefig(output_path("output_essay_paralchain_workload_change" + str(index) + ".jpg"))
            fig.clf()
            continue

        axins = ax.inset_axes((0.58, 0.15, 0.4, 0.3))
        axins.plot(
            xToR,
            yToR,
            color="#055DF3",
            alpha=0.8,
            marker="D",
            label="ToR",
            linewidth=3,
            mew=5,
            ms=1
        )
        axins.plot(
            xAoR,
            yAoR,
            color="#E67E22",
            alpha=0.8,
            marker="s",
            label="AoR",
            linewidth=3,
            mew=5,
            ms=1
        )

        xlim0 = 10
        xlim1 = 30
        ylim0 = 0 - 10
        ylim1 = 100
        axins.set_xlim(xlim0, xlim1)
        axins.set_ylim(ylim0, ylim1)

        # 填充颜色
        ax0 = xlim0
        ax1 = xlim1
        ay0 = ylim0
        ay1 = ylim1
        axins_sx = [ax0, ax1, ax1, ax0, ax0]
        axins_sy = [ay0, ay0, ay1, ay1, ay0]

        axins.fill(axins_sx, axins_sy, color="#FFFACD")

        tx0 = xlim0
        tx1 = xlim1
        ty0 = ylim0 - 20
        ty1 = ylim1
        sx = [tx0, tx1, tx1, tx0, tx0]
        sy = [ty0, ty0, ty1, ty1, ty0]
        ax.plot(sx, sy, "black")

        xy = (xlim1, ylim1)
        xy2 = (xlim0, ylim1)
        con = ConnectionPatch(
            xyA=xy2,
            xyB=xy,
            coordsA="data",
            coordsB="data",
            axesA=axins,
            axesB=ax,
            linestyle="dotted",
        )
        axins.add_artist(con)

        xy = (xlim1, ylim0 - 20)  
        xy2 = (xlim0, ylim0) 
        con = ConnectionPatch(
            xyA=xy2,
            xyB=xy,
            coordsA="data",
            coordsB="data",
            axesA=axins,
            axesB=ax,
            linestyle="dotted",
        )
        axins.add_artist(con)

        fig.savefig(output_path("output_essay_paralchain_workload_change" + str(index) + ".jpg"))
        fig.clf()


def essay_total_latency():
    data = Data()
    index = 0
    # for pn, value in sorted(data.pn_rt_tor.items(), key=lambda x: x[0]):
    for pn in [10, 60, 120, 180]:
        fig = plt.figure(figsize=(9, 7))
        plt.rcParams["font.weight"] = "bold"
        plt.rcParams["axes.labelweight"] = "bold"
        SMALL_SIZE = 20
        MEDIUM_SIZE = 26
        plt.rc("font", size=MEDIUM_SIZE)  # controls default text sizes
        plt.rc("axes", labelsize=MEDIUM_SIZE)  # fontsize of the x and y labels
        plt.rc("xtick", labelsize=SMALL_SIZE)  # fontsize of the tick labels
        plt.rc("ytick", labelsize=SMALL_SIZE)  # fontsize of the tick labels
        plt.rc("legend", fontsize=SMALL_SIZE)  # legend fontsize
        plt.rc("figure", titlesize=MEDIUM_SIZE)  # fontsize of the figure title
        # fig.suptitle("total_latency", fontsize=16)
        fig.tight_layout()
        plt.subplots_adjust(
            left=None, bottom=None, right=None, top=None, wspace=0.1, hspace=0.1
        )
        x, y = getxy("latency_avg", data.pn_rt_tor.get(pn, {}))
        x1, y1 = getxy("latency_avg", data.pn_rt_aor.get(pn, {}))
        x2, y2 = getxy("latency_avg", data.pn_rt_nor.get(pn, {}))
        index += 1
        ax = plt.subplot(1, 1, 1)
        ax.set_title(f"pn={pn}")
        ax.set_xlabel("ratio", labelpad=0.5)
        ax.set_ylabel("latency(sec)", labelpad=0.5)
        ax.set_ylim(ymin=0, ymax=250)
        ax.plot(x, y, label="ToR", marker="D", linewidth=5, mew=10, ms=10)
        ax.plot(x1, y1, label="AoR", marker="s", linewidth=5, mew=10, ms=10)
        ax.plot(x2, y2, label="NoR", marker="^", linewidth=5, mew=10, ms=10)
        ax.legend()
        if pn == 10:
            xToR = x
            yToR = y
            xAoR = x1
            yAoR = y1
            xNoR = x2
            yNoR = y2
            axins = ax.inset_axes((0.15, 0.4, 0.37, 0.25))
            axins.plot(
                xToR,
                yToR,
                color="#055DF3",
                alpha=0.8,
                marker="D",
                label="ToR",
                linewidth=5,
                mew=10,
                ms=10,
            )
            axins.plot(
                xAoR,
                yAoR,
                color="#E67E22",
                alpha=0.8,
                marker="s",
                label="AoR",
                linewidth=5,
                mew=10,
                ms=10,
            )
            axins.plot(
                xNoR,
                yNoR,
                color="green",
                alpha=0.8,
                marker="^",
                label="NoR",
                linewidth=5,
                mew=10,
                ms=10,
            )

            xlim0 = 0.2
            xlim1 = 0.5
            ylim0 = 10
            ylim1 = 30
            axins.set_xlim(xlim0, xlim1)
            axins.set_ylim(ylim0, ylim1)

            # # 填充颜色
            ax0 = xlim0
            ax1 = xlim1
            ay0 = ylim0
            ay1 = ylim1
            axins_sx = [ax0, ax1, ax1, ax0, ax0]
            axins_sy = [ay0, ay0, ay1, ay1, ay0]

            axins.fill(axins_sx, axins_sy, color="#FFFACD")

            tx0 = xlim0 - 0.03
            tx1 = xlim1
            ty0 = ylim0 - 5
            ty1 = ylim1 + 5
            sx = [tx0, tx1, tx1, tx0, tx0]
            sy = [ty0, ty0, ty1, ty1, ty0]
            ax.plot(sx, sy, "black")

            xy = (xlim1, ylim1 + 5)
            xy2 = (xlim1, ylim0)
            con = ConnectionPatch(
                xyA=xy2,
                xyB=xy,
                coordsA="data",
                coordsB="data",
                axesA=axins,
                axesB=ax,
                linestyle="dotted",
            )
            axins.add_artist(con)

            xy = (xlim0 - 0.03, ylim1 + 5)  
            xy2 = (xlim0, ylim0)  
            con = ConnectionPatch(
                xyA=xy2,
                xyB=xy,
                coordsA="data",
                coordsB="data",
                axesA=axins,
                axesB=ax,
                linestyle="dotted",
            )
            axins.add_artist(con)
        elif pn == 60:
            xToR = x
            yToR = y
            xAoR = x1
            yAoR = y1
            xNoR = x2
            yNoR = y2
            axins = ax.inset_axes((0.15, 0.4, 0.37, 0.25))
            axins.plot(
                xToR,
                yToR,
                color="#055DF3",
                alpha=0.8,
                marker="D",
                label="ToR",
                linewidth=5,
                mew=10,
                ms=10,
            )
            axins.plot(
                xAoR,
                yAoR,
                color="#E67E22",
                alpha=0.8,
                marker="s",
                label="AoR",
                linewidth=5,
                mew=10,
                ms=10,
            )
            axins.plot(
                xNoR,
                yNoR,
                color="green",
                alpha=0.8,
                marker="^",
                label="NoR",
                linewidth=5,
                mew=10,
                ms=10,
            )

            xlim0 = 0.2
            xlim1 = 0.5
            ylim0 = 0
            ylim1 = 50
            axins.set_xlim(xlim0, xlim1)
            axins.set_ylim(ylim0, ylim1)

            ax0 = xlim0
            ax1 = xlim1
            ay0 = ylim0
            ay1 = ylim1
            axins_sx = [ax0, ax1, ax1, ax0, ax0]
            axins_sy = [ay0, ay0, ay1, ay1, ay0]

            axins.fill(axins_sx, axins_sy, color="#FFFACD")

            tx0 = xlim0 - 0.03
            tx1 = xlim1
            ty0 = ylim0 + 5
            ty1 = ylim1
            sx = [tx0, tx1, tx1, tx0, tx0]
            sy = [ty0, ty0, ty1, ty1, ty0]
            ax.plot(sx, sy, "black")

            xy = (xlim1, ylim1)
            xy2 = (xlim1, ylim0)
            con = ConnectionPatch(
                xyA=xy2,
                xyB=xy,
                coordsA="data",
                coordsB="data",
                axesA=axins,
                axesB=ax,
                linestyle="dotted",
            )
            axins.add_artist(con)

            xy = (xlim0 - 0.03, ylim1) 
            xy2 = (xlim0, ylim0)  
            con = ConnectionPatch(
                xyA=xy2,
                xyB=xy,
                coordsA="data",
                coordsB="data",
                axesA=axins,
                axesB=ax,
                linestyle="dotted",
            )
            axins.add_artist(con)
        fig.savefig(output_path("output_essay_total_latency" + str(index) + ".jpg"))
        fig.clf()


def essay_rly_latency():
    data = Data()
    index = 0
    for pn in [10, 60, 120, 180]:
        fig = plt.figure(figsize=(9, 7))
        plt.rcParams["font.weight"] = "bold"
        plt.rcParams["axes.labelweight"] = "bold"
        SMALL_SIZE = 20
        MEDIUM_SIZE = 26
        plt.rc("font", size=MEDIUM_SIZE)  # controls default text sizes
        plt.rc("axes", labelsize=MEDIUM_SIZE)  # fontsize of the x and y labels
        plt.rc("xtick", labelsize=SMALL_SIZE)  # fontsize of the tick labels
        plt.rc("ytick", labelsize=SMALL_SIZE)  # fontsize of the tick labels
        plt.rc("legend", fontsize=SMALL_SIZE)  # legend fontsize
        plt.rc("figure", titlesize=MEDIUM_SIZE)  # fontsize of the figure title

        fig.tight_layout()
        plt.subplots_adjust(
            left=None, bottom=None, right=None, top=None, wspace=None, hspace=None
        )
        x, y = getxy("ts_rly_avg", data.pn_rt_tor.get(pn, {}))
        x1, y1 = getxy("ts_rly_avg", data.pn_rt_aor.get(pn, {}))
        x2, y2 = getxy("ts_rly_avg", data.pn_rt_nor.get(pn, {}))
        index += 1
        ax = plt.subplot(1, 1, 1)
        # ax = fig.add_axes([0.17, 0.12, 0.8, 0.8])
        ax.set_title(f"pn={pn}")
        ax.set_xlabel("ratio", labelpad=0.5)
        ax.set_ylabel("latency(sec)", labelpad=0.5)
        ax.set_ylim(ymin=0, ymax=130)
        ax.plot(x, y, label="ToR", marker="D", linewidth=5, mew=10, ms=10)
        ax.plot(x1, y1, label="AoR", marker="s", linewidth=5, mew=10, ms=10)
        ax.plot(x2, y2, label="NoR", marker="^", linewidth=5, mew=10, ms=10)
        ax.legend()
        if pn == 10:
            xToR = x
            yToR = y
            xAoR = x1
            yAoR = y1
            xNoR = x2
            yNoR = y2
            axins = ax.inset_axes((0.15, 0.45, 0.37, 0.25))
            axins.plot(
                xToR,
                yToR,
                color="#055DF3",
                alpha=0.8,
                marker="D",
                label="ToR",
                linewidth=5,
                mew=10,
                ms=10,
            )
            axins.plot(
                xAoR,
                yAoR,
                color="#E67E22",
                alpha=0.8,
                marker="s",
                label="AoR",
                linewidth=5,
                mew=10,
                ms=10,
            )
            axins.plot(
                xNoR,
                yNoR,
                color="green",
                alpha=0.8,
                marker="^",
                label="NoR",
                linewidth=5,
                mew=10,
                ms=10,
            )

            xlim0 = 0.2
            xlim1 = 0.5
            ylim0 = 0
            ylim1 = 20
            axins.set_xlim(xlim0, xlim1)
            axins.set_ylim(ylim0, ylim1)

            ax0 = xlim0
            ax1 = xlim1
            ay0 = ylim0
            ay1 = ylim1
            axins_sx = [ax0, ax1, ax1, ax0, ax0]
            axins_sy = [ay0, ay0, ay1, ay1, ay0]

            axins.fill(axins_sx, axins_sy, color="#FFFACD")

            tx0 = xlim0 - 0.03
            tx1 = xlim1
            ty0 = ylim0 + 0.5
            ty1 = ylim1 - 6
            sx = [tx0, tx1, tx1, tx0, tx0]
            sy = [ty0, ty0, ty1, ty1, ty0]
            ax.plot(sx, sy, "black")

            xy = (xlim1, ylim1 - 6)
            xy2 = (xlim1, ylim0)
            con = ConnectionPatch(
                xyA=xy2,
                xyB=xy,
                coordsA="data",
                coordsB="data",
                axesA=axins,
                axesB=ax,
                linestyle="dotted",
            )
            axins.add_artist(con)

            xy = (xlim0 - 0.03, ylim1 - 6) 
            xy2 = (xlim0, ylim0) 
            con = ConnectionPatch(
                xyA=xy2,
                xyB=xy,
                coordsA="data",
                coordsB="data",
                axesA=axins,
                axesB=ax,
                linestyle="dotted",
            )
            axins.add_artist(con)
        elif pn == 60:
            xToR = x
            yToR = y
            xAoR = x1
            yAoR = y1
            xNoR = x2
            yNoR = y2
            axins = ax.inset_axes((0.15, 0.45, 0.37, 0.25))
            axins.plot(
                xToR,
                yToR,
                color="#055DF3",
                alpha=0.8,
                marker="D",
                label="ToR",
                linewidth=5,
                mew=10,
                ms=10,
            )
            axins.plot(
                xAoR,
                yAoR,
                color="#E67E22",
                alpha=0.8,
                marker="s",
                label="AoR",
                linewidth=5,
                mew=10,
                ms=10,
            )
            axins.plot(
                xNoR,
                yNoR,
                color="green",
                alpha=0.8,
                marker="^",
                label="NoR",
                linewidth=5,
                mew=10,
                ms=10,
            )

            xlim0 = 0.2
            xlim1 = 0.5
            ylim0 = 0
            ylim1 = 40
            axins.set_xlim(xlim0, xlim1)
            axins.set_ylim(ylim0, ylim1)
            axins.set_yticks([0, 20, 40])

            ax0 = xlim0
            ax1 = xlim1
            ay0 = ylim0
            ay1 = ylim1
            axins_sx = [ax0, ax1, ax1, ax0, ax0]
            axins_sy = [ay0, ay0, ay1, ay1, ay0]

            axins.fill(axins_sx, axins_sy, color="#FFFACD")

            tx0 = xlim0 - 0.03
            tx1 = xlim1
            ty0 = ylim0 + 2
            ty1 = ylim1 - 10
            sx = [tx0, tx1, tx1, tx0, tx0]
            sy = [ty0, ty0, ty1, ty1, ty0]
            ax.plot(sx, sy, "black")

            xy = (xlim1, ylim1 - 10)
            xy2 = (xlim1, ylim0)
            con = ConnectionPatch(
                xyA=xy2,
                xyB=xy,
                coordsA="data",
                coordsB="data",
                axesA=axins,
                axesB=ax,
                linestyle="dotted",
            )
            axins.add_artist(con)

            xy = (xlim0 - 0.03, ylim1 - 10) 
            xy2 = (xlim0, ylim0) 
            con = ConnectionPatch(
                xyA=xy2,
                xyB=xy,
                coordsA="data",
                coordsB="data",
                axesA=axins,
                axesB=ax,
                linestyle="dotted",
            )
            axins.add_artist(con)
        fig.savefig(output_path("output_essay_rly_latency" + str(index) + ".jpg"))
        fig.clf()


def essay_rly_latency_adpat():
    data = Data()
    ncol = 2
    nrow = 2
    index = 0
    fig = plt.figure(figsize=(ncol * 3, nrow * 3))
    # fig.suptitle("rly latency avg", fontsize=16)
    fig.tight_layout()
    plt.subplots_adjust(
        left=None, bottom=None, right=None, top=None, wspace=0.3, hspace=0.5
    )
    for pn in [10, 60, 120, 180]:
        x, y = getxy("ts_rly_avg", data.pn_rt_tor.get(pn, {}))
        x1, y1 = getxy("ts_rly_avg", data.pn_rt_aor.get(pn, {}))
        x2, y2 = getxy("ts_rly_avg", data.pn_rt_nor.get(pn, {}))
        index += 1
        ax = plt.subplot(
            nrow,
            ncol,
            index,
        )
        ax.set_title(f"pn={pn}")
        ax.set_xlabel("ratio")
        ax.set_ylabel("latency(sec)")
        # ax.set_ylim(ymin=0, ymax=230)
        ax.plot(x, y, label="ToR", marker="D")
        ax.plot(x1, y1, label="AoR", marker="s")
        ax.plot(x2, y2, label="NoR", marker="^")
        ax.legend()
    # lines, labels = fig.axes[-1].get_legend_handles_labels()
    # fig.legend(lines, labels, loc="center left")
    fig.savefig(output_path("output_essay_rly_latency_adapt.jpg"))


def essay_tps():
    data = Data()
    index = 0

    for pn in [10, 60, 120, 180]:
        fig = plt.figure(figsize=(9, 7))
        plt.rcParams["font.weight"] = "bold"
        plt.rcParams["axes.labelweight"] = "bold"
        SMALL_SIZE = 20
        MEDIUM_SIZE = 26
        plt.rc("font", size=MEDIUM_SIZE)  # controls default text sizes
        plt.rc("axes", labelsize=MEDIUM_SIZE)  # fontsize of the x and y labels
        plt.rc("xtick", labelsize=SMALL_SIZE)  # fontsize of the tick labels
        plt.rc("ytick", labelsize=SMALL_SIZE)  # fontsize of the tick labels
        plt.rc("legend", fontsize=SMALL_SIZE)  # legend fontsize
        plt.rc("figure", titlesize=MEDIUM_SIZE)  # fontsize of the figure title
        fig.tight_layout()
        plt.subplots_adjust(
            left=None, bottom=None, right=None, top=None, wspace=0.1, hspace=0.1
        )
        x, y = getxy("tps", data.pn_rt_tor.get(pn, {}))
        x1, y1 = getxy("tps", data.pn_rt_aor.get(pn, {}))
        x2, y2 = getxy("tps", data.pn_rt_nor.get(pn, {}))
        index += 1
        ax = plt.subplot(1, 1, 1)
        ax.set_title(f"pn={pn}")
        ax.set_xlabel("ratio", labelpad=0.5)
        if index in [1, 2]:
            ax.set_ylabel("TPS", labelpad=0.5)
        else:
            ax.set_ylabel("TPS", labelpad=-10)
        # ax.set_ylim(ymin=0, ymax=1200)
        ax.plot(x, y, label="ToR", marker="D", linewidth=5, mew=10, ms=10)
        ax.plot(x1, y1, label="AoR", marker="s", linewidth=5, mew=10, ms=10)
        ax.plot(x2, y2, label="NoR", marker="^", linewidth=5, mew=10, ms=10)
        ax.legend(loc="upper left")
        # ax.legend()
        # fig.legend(loc="upper left")
        fig.savefig(output_path("output_essay_tps" + str(index) + ".jpg"))
        fig.clf()


def essay_inter_load_avg():
    data = Data()
    index = 0
    total_width, n = 0.2, 2
    width = total_width / n
    width = width / 3 * 2
    for pn in [60, 180]:
        fig = plt.figure(figsize=(9, 8))
        fig.tight_layout()
        plt.subplots_adjust(
            left=None, bottom=None, right=None, top=None, wspace=0.1, hspace=0.1
        )
        plt.rcParams["font.weight"] = "bold"
        plt.rcParams["axes.labelweight"] = "bold"
        SMALL_SIZE = 20
        MEDIUM_SIZE = 26
        plt.rc("font", size=MEDIUM_SIZE)  # controls default text sizes
        plt.rc("axes", labelsize=MEDIUM_SIZE)  # fontsize of the x and y labels
        plt.rc("xtick", labelsize=SMALL_SIZE)  # fontsize of the tick labels
        plt.rc("ytick", labelsize=SMALL_SIZE)  # fontsize of the tick labels
        plt.rc("legend", fontsize=SMALL_SIZE)  # legend fontsize
        plt.rc("figure", titlesize=MEDIUM_SIZE)  # fontsize of the figure title

        x, y = getxy("inter_load_avg", data.pn_rt_tor.get(pn, {}))
        y = [math.log(x, 2) for x in y]
        x1, y1 = getxy("inter_load_avg", data.pn_rt_aor.get(pn, {}))
        y1 = [math.log(x, 2) for x in y1]

        xx, yy = getxy("inter_load_max", data.pn_rt_tor.get(pn, {}))
        yy = [math.log(x, 2) for x in yy]
        xx1, yy1 = getxy("inter_load_max", data.pn_rt_aor.get(pn, {}))
        yy1 = [math.log(x, 2) for x in yy1]

        index += 1
        # ax = plt.subplot(
        #     1,1,1
        # )
        ax = fig.add_axes([0.1, 0.1, 0.8, 0.7])
        ax.set_title(f"pn={pn}")
        ax.set_xlabel("ratio", labelpad=0.5)
        ax.set_ylabel("tx number", labelpad=0.5)
        # ax.set_ylim(ymin=0, ymax=160)
        ax.plot(x, y, label="ToR-avg", marker="D", linewidth=5, mew=10, ms=10)
        ax.plot(x1, y1, label="AoR-avg", marker="s", linewidth=5, mew=10, ms=10)
        ax.bar(
            [i - width / 2 for i in xx],
            yy,
            width=width,
            label="ToR-max",
            color="white",
            edgecolor="blue",
            hatch="....",
        )
        ax.bar(
            [i + width / 2 for i in xx1],
            yy1,
            width=width,
            label="AoR-max",
            color="white",
            edgecolor="orange",
            hatch="////",
        )
        lines, labels = fig.axes[-1].get_legend_handles_labels()
        fig.legend(lines, labels, loc="upper center", ncol=2)
        # fig.legend(lines, labels, loc="upper center", ncol=4,columnspacing=0.3,bbox_to_anchor=(0.5, 1.02),frameon=False)
        fig.savefig(output_path("output_essay_inter_load_avg" + str(index) + ".jpg"))
        fig.clf()
    # inter workload reverse
    for ratio in [0.2, 0.8]:
        total_width, n = 30, 2
        width = total_width / n
        width = width / 3 * 2
       
        x, y = getxy("inter_load_avg", data.rt_pn_tor.get(ratio, {}))
        x_step = x[::3]
        y_step = y[::3]
        y = [math.log(x, 2) for x in y_step]
        x1, y1 = getxy("inter_load_avg", data.rt_pn_aor.get(ratio, {}))
        x1_step = x1[::3]
        y1_step = y1[::3]
        y1 = [math.log(x, 2) for x in y1_step]

        xx, yy = getxy("inter_load_max", data.rt_pn_tor.get(ratio, {}))
        yy = [math.log(x, 2) for x in yy]
        xx1, yy1 = getxy("inter_load_max", data.rt_pn_aor.get(ratio, {}))
        yy1 = [math.log(x, 2) for x in yy1]

        index += 1
        
        ax = fig.add_axes([0.1, 0.1, 0.8, 0.7])
        ax.set_title(f"ratio={ratio}")
        ax.set_xlabel("pn", labelpad=0.5)
        ax.set_ylabel("tx", labelpad=0.5)
        # ax.set_ylim(ymin=0, ymax=160)
        ax.plot(x_step, y, label="ToR-avg", marker="D", linewidth=5, mew=10, ms=10)
        ax.plot(x1_step, y1, label="AoR-avg", marker="s", linewidth=5, mew=10, ms=10)
        # ax.legend()
        ax.bar(
            [i - width / 2 for i in xx[::3]],
            yy[::3],
            width=width,
            label="ToR-max",
            color="white",
            edgecolor="blue",
            hatch="....",
        )
        ax.bar(
            [i + width / 2 for i in xx1[::3]],
            yy1[::3],
            width=width,
            label="AoR-max",
            color="white",
            edgecolor="orange",
            hatch="////",
        )

        lines, labels = fig.axes[-1].get_legend_handles_labels()
        fig.legend(lines, labels, loc="upper center", ncol=2)
        # fig.legend(lines, labels, loc="upper center", ncol=4,columnspacing=0.3,bbox_to_anchor=(0.5, 1.02),frameon=False)
        fig.savefig(output_path("output_essay_inter_load_avg" + str(index) + ".jpg"))
        fig.clf()


def essay_scalability():
    data = Data()

    ncol = 2
    nrow = 1
    index = 0
    fig = plt.figure(figsize=(ncol * 3, nrow * 3))
    # fig.suptitle("total_latency", fontsize=16)
    fig.tight_layout()
    plt.subplots_adjust(
        left=None, bottom=0.2, right=None, top=0.8, wspace=0.4, hspace=0.5
    )
    for ratio in [0.8]:
        x, y = getxy("tps", data.rt_pn_tor.get(ratio, {}))
        x1, y1 = getxy("tps", data.rt_pn_aor.get(ratio, {}))
        x2, y2 = getxy("tps", data.rt_pn_nor.get(ratio, {}))
        index += 1
        ax = plt.subplot(
            nrow,
            ncol,
            index,
        )
        ax.set_title(f"ratio={ratio}")
        ax.set_xlabel("pn")
        ax.set_ylabel("TPS")
        # ax.set_ylim(ymin=10, ymax=500)
        ax.plot(x, y, label="ToR", marker="D")
        ax.plot(x1, y1, label="AoR", marker="s")
        ax.plot(x2, y2, label="NoR", marker="^")
        ax.legend()
    for ratio in [0.8]:
        x, y = getxy("latency_avg", data.rt_pn_tor.get(ratio, {}))
        x1, y1 = getxy("latency_avg", data.rt_pn_aor.get(ratio, {}))
        x2, y2 = getxy("latency_avg", data.rt_pn_nor.get(ratio, {}))
        index += 1
        print(nrow, ncol, index)
        ax = plt.subplot(
            nrow,
            ncol,
            index,
        )
        ax.set_title(f"ratio={ratio}")
        ax.set_xlabel("pn")
        ax.set_ylabel("latency(sec)")
        ax.set_ylim(ymin=0, ymax=250)
        ax.plot(x, y, label="ToR", marker="D")
        ax.plot(x1, y1, label="AoR", marker="s")
        ax.plot(x2, y2, label="NoR", marker="^")
        ax.legend()
      
    # lines, labels = fig.axes[-1].get_legend_handles_labels()
    # fig.legend(lines, labels, loc="upper left")
    fig.savefig(output_path("output_essay_scalability.jpg"))


def essay_inter_workload_ratio():
    data = Data()
    ncol = 1
    nrow = 1
    index = 0
    fig = plt.figure(figsize=(9, 9))
    # fig = plt.figure()
    # fig.suptitle("all txs number on relaychain", fontsize=16)
    fig.tight_layout()
    plt.subplots_adjust(
        left=None, bottom=None, right=None, top=None, wspace=None, hspace=0.5
    )
    index += 1
    ax = plt.subplot(
        nrow,
        ncol,
        index,
    )
    # ax.set_title(f"reduction of relaychain's load", fontdict={'fontsize': 16})
    ax.set_xlabel("ratio")
    ax.set_ylabel("optimization ratio")
    # ax.set_ylim(0.8, 1.0)
    markers = [
        "o",
        "^",
        "v",
        "1",
        "*",
        "s",
        "D",
        "p",
        "X",
        "x",
        "P",
        "o",
        "^",
        "v",
        "1",
        "*",
        "s",
        "D",
        "p",
        "X",
        "x",
        "P",
    ]
    marker_id = 0
    maxv = 0
    minv = 100
    sumv = []
    for pn, value in sorted(data.pn_rt_tor.items(), key=lambda x: x[0]):
        x, y = getxy("inter_load_avg", data.pn_rt_tor.get(pn, {}))
        x1, y1 = getxy("inter_load_avg", data.pn_rt_aor.get(pn, {}))
        # rx, ry = getxy("workload_opt_ratio", data.pn_rt_tor[pn])
        # rx1, ry1 = getxy("workload_opt_ratio", data.pn_rt_aor[pn])
        bnx, bny = getxy("paral_bn_avg", data.pn_rt_tor[pn])
        bnx1, bny1 = getxy("paral_bn_avg", data.pn_rt_aor[pn])
        ratios = [
            workload_optimization_ratio((y + y1) / 2) for (y, y1) in zip(bny, bny1)
        ]

        a, b = x, [1 - p / p1 for (p, p1) in zip(y, y1)]
        bavg = sum(b) / len(b)
        diff2 = (sum((x - bavg) ** 2 for x in b) / len(b)) ** (1 / 2)
        print(f"diff2 of pn({pn}): {diff2}")
        # a, b = x, [1-math.log(p,2)/math.log(p1, 2) for (p, p1) in zip(y, y1)]
        maxv = max(maxv, max(b))
        minv = min(minv, min(b))
        sumv.extend(b)
        c = [1 - r0 / r1 for (r0, r1) in zip(b, ratios)]
        ax.plot(a, c, label=str(pn), marker=markers[marker_id], markersize=10)
        marker_id += 1
    # ax.axhline(y=maxv, color="green", xmin=0, xmax=1.0, linewidth=1, linestyle="dashed")
    # ax.text(0.3, maxv - 0.003, s=f"max={maxv:.2f}", fontsize=10, color="green")
    # ax.axhline(y=minv, color="green", xmin=0, xmax=1.0, linewidth=1, linestyle="dashed")
    # ax.text(0.3, minv + 0.003, s=f"min={minv:.2f}", fontsize=10, color="green")
    # avgv = sum(sumv) / len(sumv)
    # ax.axhline(y=avgv, color="red", xmin=0, xmax=1.0, linewidth=2, linestyle="dashed")
    # ax.text(0.7, avgv - 0.003, s=f"avg={avgv:.2f}", fontsize=14, color="r")
    ax.legend()
    fig.savefig(output_path("output_essay_inter_workload_ratio.jpg"))


def test_data():
    data = Data()
    json.dump(data.pn_rt_tor, open("temp/test_data.json", "w"))


if __name__ == "__main__":
    # test_data()
    # total_latency()
    # total_latency_reverse()
    # total_latency_simple()
    # tps()
    # tps_reverse()
    # rly_latency()
    # inter_duration()
    # inter_ratio()
    # inter_ratio_reverse()
    # inter_totaltxs()
    # inter_load_avg()
    # inter_load_avg_reverse()
    # paral_load_avg()
    # paral_load_avg_reverse()
    # paral_workload_change()
    # inter_load_avg_simple()
    # inter_load_delta()
    # inter_load_max()

    essay_paral_workload_change()
    # essay_total_latency()
    # essay_rly_latency()
    # essay_rly_latency_adpat()  # y轴刻度不同
    # essay_tps()
    # essay_inter_load_avg()
    # essay_scalability()
    # essay_inter_workload_ratio()

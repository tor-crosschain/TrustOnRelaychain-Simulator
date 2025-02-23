import os
import math
import json
from matplotlib import pyplot as plt
import matplotlib.pylab as pylab

params = {
    "legend.fontsize": "xx-large",
    "figure.figsize": (15, 5),
    "figure.titlesize": "xx-large",
    "axes.labelsize": "xx-large",
    "axes.titlesize": "xx-large",
    "xtick.labelsize": "xx-large",
    "ytick.labelsize": "xx-large",
}
pylab.rcParams.update(params)


datapath_tor = "./evaluation/data/ToR.json"
datapath_aor = "./evaluation/data/AoR.json"
datapath_nor = "./evaluation/data/NoR.json"

output_dir = "./evaluation/analysis/"


def output_path(img_name: str) -> str:
    return os.path.join(os.path.abspath(output_dir), img_name)


class Data:
    ToR = json.load(open(datapath_tor, "r"))
    AoR = json.load(open(datapath_aor, "r"))
    NoR = json.load(open(datapath_nor, "r"))

    def __init__(self) -> None:
        self.pn_rt_tor = {}
        self.pn_rt_aor = {}
        self.pn_rt_nor = {}
        self.rt_pn_tor = {}
        self.rt_pn_aor = {}
        self.rt_pn_nor = {}
        self.read_tor()
        self.read_aor()
        self.read_nor()

    def read_tor(self):
        for item in Data.ToR:
            pn = item["para_num"]
            rt = item["xtx_ratio"]
            interalltxs = item["interalltxs"]
            interdur = item.get("interdur", 0)  # Total processing time on the relay chain
            tps = item["tps"]
            latency_avg = item["latency_avg"]
            ts_src_avg = item["ts_src_avg"]
            ts_rly_avg = item["ts_rly_avg"]
            ts_dst_avg = item["ts_dst_avg"]
            inter_load_file = item["inter_loads"]
            inter_loads = json.load(open(inter_load_file, "r"))
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
            self.pn_rt_tor[pn][rt] = data
            if self.rt_pn_tor.get(rt, None) is None:
                self.rt_pn_tor[rt] = {}
            self.rt_pn_tor[rt][pn] = data

        for pn, rt in self.pn_rt_tor.items():
            for ratio, data in rt.items():
                for key, value in data.items():
                    sample = sorted(value)
                    if len(sample) > 1:
                        sample = sample[:-1]
                    data[key] = float(f"{sum(sample)/len(sample):.3f}")
                self.pn_rt_tor[pn][ratio] = data
                self.rt_pn_tor[ratio][pn] = data

    def read_aor(self):
        for item in Data.AoR:
            pn = item["para_num"]
            rt = item["xtx_ratio"]
            interalltxs = item["interalltxs"]
            interdur = item.get("interdur", 0)  # Total processing time on the relay chain
            tps = item["tps"]
            latency_avg = item["latency_avg"]
            ts_src_avg = item["ts_src_avg"]
            ts_rly01_avg = item["ts_rly01_avg"]
            ts_inter_avg = item["ts_inter_avg"]
            ts_rly02_avg = item["ts_rly02_avg"]
            ts_dst_avg = item["ts_dst_avg"]
            inter_load_file = item["inter_loads"]
            inter_loads = json.load(open(inter_load_file, "r"))
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
            self.pn_rt_aor[pn][rt] = data
            if self.rt_pn_aor.get(rt, None) is None:
                self.rt_pn_aor[rt] = {}
            self.rt_pn_aor[rt][pn] = data

        for pn, rt in self.pn_rt_aor.items():
            for ratio, data in rt.items():
                for key, value in data.items():
                    sample = sorted(value)
                    if len(sample) > 1:
                        sample = sample[:-1]
                    data[key] = float(f"{sum(sample)/len(sample):.3f}")
                self.pn_rt_aor[pn][ratio] = data
                self.rt_pn_aor[ratio][pn] = data

    def read_nor(self):
        for item in Data.NoR:
            pn = item["para_num"]
            rt = item["xtx_ratio"]
            interalltxs = item["interalltxs"]
            interdur = item.get("interdur", 0) 
            tps = item["tps"]
            latency_avg = item["latency_avg"]
            ts_src_avg = item["ts_src_avg"]
            ts_rly_avg = item["ts_rly_avg"]
            ts_dst_avg = item["ts_dst_avg"]
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
            self.pn_rt_nor[pn][rt] = data
            if self.rt_pn_nor.get(rt, None) is None:
                self.rt_pn_nor[rt] = {}
            self.rt_pn_nor[rt][pn] = data

        for pn, rt in self.pn_rt_nor.items():
            for ratio, data in rt.items():
                for key, value in data.items():
                    sample = sorted(value)
                    if len(sample) > 1:
                        sample = sample[:-1]
                    data[key] = float(f"{sum(sample)/len(sample):.3f}")
                self.pn_rt_nor[pn][ratio] = data
                self.rt_pn_nor[ratio][pn] = data


def getxy(key: str, data: dict) -> [list, list]:
    ts_rly_avg = [(rt, y[key]) for rt, y in data.items()]
    ts_rly_avg = sorted(ts_rly_avg, key=lambda x: x[0])
    x = [item[0] for item in ts_rly_avg]
    y = [item[1] for item in ts_rly_avg]
    return x, y


def total_latency():
    data = Data()
    ncol = 3
    nrow = len(data.pn_rt_tor) // ncol
    index = 0
    fig = plt.figure(figsize=(13, 6))
    fig.suptitle("total latency", fontsize=20)
    fig.tight_layout()
    plt.subplots_adjust(
        left=None, bottom=None, right=None, top=None, wspace=0.3, hspace=0.5
    )
    for pn, value in data.pn_rt_tor.items():
        # 随跨链交易比例变化
        x, y = getxy("latency_avg", data.pn_rt_tor[pn])
        x1, y1 = getxy("latency_avg", data.pn_rt_aor[pn])
        x2, y2 = getxy("latency_avg", data.pn_rt_nor[pn])
        index += 1
        ax = plt.subplot(
            nrow,
            ncol,
            index,
        )
        ax.set_title(f"paranum={pn}", fontsize=16)
        ax.set_xlabel("ratio", fontsize=16)
        ax.set_ylabel("latency(sec)", fontsize=16)
        ax.set_ylim(ymin=0, ymax=140)
        ax.tick_params(labelsize=12)
        ax.plot(x, y, label="ToR", marker="D")
        ax.plot(x1, y1, label="AoR", marker="s")
        ax.plot(x2, y2, label="NoR", marker="^")
        # ax.legend()
    lines, labels = fig.axes[-1].get_legend_handles_labels()
    fig.legend(lines, labels, loc="center left", prop={"size": 12})
    fig.savefig(output_path("output_total_latency.jpg"))


def rly_latency():
    data = Data()
    ncol = 3
    nrow = len(data.pn_rt_tor) // ncol
    index = 0
    fig = plt.figure(figsize=(13, 6))
    fig.suptitle("relay latency avg", fontsize=20)
    fig.tight_layout()
    plt.subplots_adjust(
        left=None, bottom=None, right=None, top=None, wspace=0.3, hspace=0.5
    )
    for pn, value in data.pn_rt_tor.items():
        # change as cross-chain transaction ratio varies
        x, y = getxy("ts_rly_avg", data.pn_rt_tor[pn])
        x1, y1 = getxy("ts_rly_avg", data.pn_rt_aor[pn])
        x2, y2 = getxy("ts_rly_avg", data.pn_rt_nor[pn])
        index += 1
        ax = plt.subplot(
            nrow,
            ncol,
            index,
        )
        ax.set_title(f"paranum={pn}", fontsize=16)
        ax.set_xlabel("ratio", fontsize=16)
        ax.set_ylabel("latency(sec)", fontsize=16)
        ax.set_ylim(ymin=0, ymax=130)
        ax.tick_params(labelsize=12)
        ax.plot(x, y, label="ToR", marker="D")
        ax.plot(x1, y1, label="AoR", marker="s")
        ax.plot(x2, y2, label="NoR", marker="^")
        # ax.legend()
    lines, labels = fig.axes[-1].get_legend_handles_labels()
    fig.legend(lines, labels, loc="center left", prop={"size": 12})
    fig.savefig(output_path("output_rly_latency.jpg"))


def inter_duration():
    data = Data()
    ncol = 3
    nrow = len(data.pn_rt_tor) // ncol
    index = 0
    fig = plt.figure(figsize=(13, 6))
    fig.suptitle("inter total duration", fontsize=16)
    fig.tight_layout()
    plt.subplots_adjust(
        left=None, bottom=None, right=None, top=None, wspace=0.3, hspace=0.5
    )
    for pn, value in data.pn_rt_tor.items():
        # change as cross-chain transaction ratio varies
        x, y = getxy("interdur", data.pn_rt_tor[pn])
        x1, y1 = getxy("interdur", data.pn_rt_aor[pn])
        index += 1
        ax = plt.subplot(
            nrow,
            ncol,
            index,
        )
        ax.set_title(f"paranum={pn}")
        ax.set_xlabel("ratio")
        ax.set_ylabel("latency(sec)")
        ax.set_ylim(ymin=0, ymax=250)
        ax.plot(x, y, label="ToR", marker="D")
        ax.plot(x1, y1, label="AoR", marker="s")
        ax.legend()
    lines, labels = fig.axes[-1].get_legend_handles_labels()
    fig.legend(lines, labels, loc="center left")
    fig.savefig(output_path("output_inter_duration.jpg"))


def tps():
    data = Data()
    ncol = 3
    nrow = len(data.pn_rt_tor) // ncol
    index = 0
    fig = plt.figure(figsize=(13, 6))
    fig.suptitle("TPS", fontsize=24)
    fig.tight_layout()
    plt.subplots_adjust(
        left=None, bottom=None, right=None, top=None, wspace=0.3, hspace=0.5
    )

    for pn, value in data.pn_rt_tor.items():
        x, y = getxy("tps", data.pn_rt_tor[pn])
        x1, y1 = getxy("tps", data.pn_rt_aor[pn])
        x2, y2 = getxy("tps", data.pn_rt_nor[pn])
        index += 1
        ax = plt.subplot(
            nrow,
            ncol,
            index,
        )
        ax.set_title(f"paranum={pn}", fontsize=16)
        ax.set_xlabel("ratio", fontsize=16)
        ax.set_ylabel("TPS", fontsize=16)
        ax.set_ylim(ymin=10, ymax=500)
        ax.tick_params(labelsize=10)
        ax.plot(x, y, label="ToR", marker="D")
        ax.plot(x1, y1, label="AoR", marker="s")
        ax.plot(x2, y2, label="NoR", marker="^")

    lines, labels = fig.axes[-1].get_legend_handles_labels()
    fig.legend(lines, labels, loc="center left", prop={"size": 12})
    fig.savefig(output_path("output_tps.jpg"))


def tps_reverse():
    data = Data()
    ncol = 5
    nrow = len(data.pn_rt_tor) // ncol
    index = 0
    fig = plt.figure(figsize=(30, 5))
    fig.suptitle("TPS", fontsize=16)
    fig.tight_layout()
    plt.subplots_adjust(
        left=None, bottom=None, right=None, top=None, wspace=0.3, hspace=0.5
    )
    for ratio, value in data.rt_pn_tor.items():
        # change as cross-chain transaction ratio varies
        x, y = getxy("tps", data.rt_pn_tor[ratio])
        x1, y1 = getxy("tps", data.rt_pn_aor[ratio])
        x2, y2 = getxy("tps", data.rt_pn_nor[ratio])
        index += 1
        ax = plt.subplot(
            nrow,
            ncol,
            index,
        )
        ax.set_title(f"ratio={ratio}")
        ax.set_xlabel("paranum")
        ax.set_ylabel("TPS")
        ax.set_ylim(ymin=10, ymax=500)
        ax.plot(x, y, label="ToR", marker="D")
        ax.plot(x1, y1, label="AoR", marker="s")
        ax.plot(x2, y2, label="NoR", marker="^")
        ax.legend()
    plt.legend()
    fig.savefig(output_path("output_tps_reverse.jpg"))


def inter_load_avg_reverse():
    data = Data()
    ncol = len(data.rt_pn_tor)
    nrow = 1
    index = 0
    fig = plt.figure(figsize=(30, 5))
    fig.suptitle("load average on relaychain (increase paranum)", fontsize=16)
    fig.tight_layout()
    plt.subplots_adjust(
        left=None, bottom=None, right=None, top=None, wspace=None, hspace=0.5
    )

    total_width, n = 10, 2
    width = total_width / n
    width = width / 3 * 2
    for ratio, value in data.rt_pn_tor.items():
        # change as cross-chain transaction ratio varies
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
        ax.set_xlabel("paranum")
        ax.set_ylabel("tx")
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
     
    fig.savefig(output_path("output_inter_load_reverse.jpg"))


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
        # change as cross-chain transaction ratio varies
        rts.add(rt)
        x, y = getxy("inter_load_avg", data.rt_pn_tor[rt])
        x = normalization(x)
        y = normalization(y)
        marker_id += 1
        ax.plot(x, y, label=f"ratio-{rt}", marker=markers[marker_id], linestyle="-")

    ax.plot(x, pns, label="paranum")
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
    fig.suptitle("total txs on relaychain", fontsize=16)
    fig.tight_layout()
    plt.subplots_adjust(
        left=None, bottom=None, right=None, top=None, wspace=None, hspace=0.5
    )

    total_width, n = 0.2, 2
    width = total_width / n
    width = width / 3 * 2
    for pn, value in data.pn_rt_tor.items():
        # change as cross-chain transaction ratio varies
        x, y = getxy("interalltxs", data.pn_rt_tor[pn])
        x1, y1 = getxy("interalltxs", data.pn_rt_aor[pn])
        index += 1
        ax = plt.subplot(
            nrow,
            ncol,
            index,
        )
        ax.set_title(f"paranum={pn}")
        ax.set_xlabel("ratio")
        ax.set_ylabel("tx/s")
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
    fig.suptitle("max load on relaychain", fontsize=16)
    fig.tight_layout()
    plt.subplots_adjust(
        left=None, bottom=None, right=None, top=None, wspace=None, hspace=0.5
    )

    total_width, n = 0.2, 2
    width = total_width / n
    width = width / 3 * 2
    for pn, value in data.pn_rt_tor.items():
        # change as cross-chain transaction ratio varies
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
        ax.set_title(f"paranum={pn}")
        ax.set_xlabel("ratio")
        ax.set_ylabel("tx")
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
    ncol = 3
    nrow = len(data.pn_rt_tor) // ncol
    index = 0
    fig = plt.figure(figsize=(13, 6))
    fig.suptitle("average load on relaychain (increase xtxratio)", fontsize=16)
    fig.tight_layout()
    plt.subplots_adjust(
        left=None, bottom=None, right=None, top=None, wspace=0.3, hspace=0.5
    )

    total_width, n = 0.2, 2
    width = total_width / n
    width = width / 3 * 2
    for pn, value in data.pn_rt_tor.items():
        # change as cross-chain transaction ratio varies
        x, y = getxy("inter_load_avg", data.pn_rt_tor[pn])
        y = [math.log(x, 2) for x in y]
        x1, y1 = getxy("inter_load_avg", data.pn_rt_aor[pn])
        y1 = [math.log(x, 2) for x in y1]

        xx, yy = getxy("inter_load_max", data.pn_rt_tor[pn])
        yy = [math.log(x, 2) for x in yy]
        xx1, yy1 = getxy("inter_load_max", data.pn_rt_aor[pn])
        yy1 = [math.log(x, 2) for x in yy1]

        index += 1
        ax = plt.subplot(
            nrow,
            ncol,
            index,
        )
        ax.set_title(f"paranum={pn}")
        ax.set_xlabel("ratio")
        ax.set_ylabel("tx number")
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
    lines, labels = fig.axes[-1].get_legend_handles_labels()
    fig.legend(lines, labels, loc="center left")
    fig.savefig(output_path("output_inter_load_avg.jpg"))


def inter_ratio():
    data = Data()
    ncol = 1
    nrow = 1
    index = 0
    fig = plt.figure(figsize=(9, 9))
    fig.suptitle("relay-chain workload optimization ratio", fontsize=20)
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
  
    ax.set_xlabel("xtx ratio")
    ax.set_ylabel("optimization ratio")
    markers = ["o", "^", "*", "s", "D", "p"]
    marker_id = 0
    maxv = 0
    minv = 100
    sumv = []
    for pn, value in data.pn_rt_tor.items():
        # change as cross-chain transaction ratio varies
        x, y = getxy("inter_load_avg", data.pn_rt_tor[pn])
        x1, y1 = getxy("inter_load_avg", data.pn_rt_aor[pn])
        a, b = x, [1 - p / p1 for (p, p1) in zip(y, y1)]
        bavg = sum(b) / len(b)
        diff2 = (sum((x - bavg) ** 2 for x in b) / len(b)) ** (1 / 2)
        print(f"diff2 of paranum({pn}): {diff2}")
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
    ax.set_xlabel("ratio")
    ax.set_ylabel("decrease ratio")
    ax.set_ylim(0.6, 1.0)
    markers = ["o", "^", "*", "s", "D", "p"]
    marker_id = 0
    maxv = 0
    minv = 100
    sumv = []
    for ratio, value in data.rt_pn_tor.items():
        # change as cross-chain transaction ratio varies
        x, y = getxy("inter_load_avg", data.rt_pn_tor[ratio])
        x1, y1 = getxy("inter_load_avg", data.rt_pn_aor[ratio])
        a, b = x, [1 - p / p1 for (p, p1) in zip(y, y1)]
        a, b = x, [1 - p / p1 for (p, p1) in zip(y, y1)]
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
    ncol = 2
    nrow = 1
    index = 0
    fig = plt.figure(figsize=(13, 6))
    fig.suptitle("relay-chain average workload", fontsize=20)
    fig.tight_layout()
    plt.subplots_adjust(
        left=None, bottom=None, right=None, top=None, wspace=0.3, hspace=0.5
    )

    total_width, n = 0.2, 2
    width = total_width / n
    width = width / 3 * 2
    pn = 35
    x, y = getxy("inter_load_avg", data.pn_rt_tor[pn])
    y = [math.log(x, 2) for x in y]
    x1, y1 = getxy("inter_load_avg", data.pn_rt_aor[pn])
    y1 = [math.log(x, 2) for x in y1]
    xx, yy = getxy("inter_load_max", data.pn_rt_tor[pn])
    yy = [math.log(x, 2) for x in yy]
    xx1, yy1 = getxy("inter_load_max", data.pn_rt_aor[pn])
    yy1 = [math.log(x, 2) for x in yy1]
    index += 1
    ax = plt.subplot(
        nrow,
        ncol,
        index,
    )
    ax.set_title(f"paranum={pn}")
    ax.set_xlabel("ratio")
    ax.set_ylabel("tx number")
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
    ax.legend(prop={"size": 14})

    total_width, n = 10, 2
    width = total_width / n
    width = width / 3 * 2
    # xtxratio=0.8, vary by paranum
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
    ax.set_xlabel("paranum")
    ax.set_ylabel("tx number")
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
    ax.legend(prop={"size": 14})

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
    ax.set_title(f"paranum={pn}")
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
    ax.set_xlabel("paranum")
    ax.set_ylabel("latency(sec)")
    # ax.set_ylim(ymin=0, ymax=140)
    ax.plot(x, y, label="ToR", marker="D")
    ax.plot(x1, y1, label="AoR", marker="s")
    ax.plot(x2, y2, label="NoR", marker="^")
    ax.legend()

    fig.savefig(output_path("output_total_latency_simple.jpg"))


def scalability_tps():
    data = Data()
    ncol = 1
    nrow = 1
    index = 0
    fig = plt.figure(figsize=(9, 9))
    fig.suptitle("Scalability", fontsize=24)
    fig.tight_layout()
    plt.subplots_adjust(
        left=None, bottom=None, right=None, top=None, wspace=0.3, hspace=0.5
    )
    indicator = "tps"
    ratio = 0.4
    x, y = getxy(indicator, data.rt_pn_tor[ratio])
    x1, y1 = getxy(indicator, data.rt_pn_aor[ratio])
    x2, y2 = getxy(indicator, data.rt_pn_nor[ratio])
    x_max, y_max = max(zip(range(len(y)), y), key=lambda a: a[1])
    x1_max, y1_max = max(zip(range(len(y1)), y1), key=lambda a: a[1])
    index += 1
    ax = plt.subplot(
        nrow,
        ncol,
        index,
    )
    ax.set_title(f"ratio={ratio}")
    ax.set_xlabel("paranum")
    ax.set_ylabel(indicator)
    ax.set_ylim(ymax=300, ymin=0)
    ax.set_xlim(xmin=0, xmax=60)
    ax.plot(x, y, label="ToR", marker="D")
    ax.plot(x1, y1, label="AoR", marker="s")
    ax.plot(x2, y2, label="NoR", marker="^")
    ax.plot([0] + x[: x_max + 1], [y_max] * (x_max + 2), linestyle="--", color="black")
    ax.plot([x[x_max], x[x_max]], [0, y_max], linestyle="--", color="black")
    ax.text(x=x[x_max] + 1, y=y_max + 5, s=f"max={y_max:.2f}", fontsize=16)
    ax.plot(
        [0] + x1[: x1_max + 1], [y1_max] * (x1_max + 2), linestyle="--", color="black"
    )
    ax.plot([x1[x1_max], x1[x1_max]], [0, y1_max], linestyle="--", color="black")
    ax.text(x=x1[x1_max] + 1, y=y1_max + 5, s=f"max={y1_max:.2f}", fontsize=16)
    ax.text(
        x=x[x_max] + 1,
        y=(y_max + y1_max) / 2,
        s=r"$\Delta $" + f"={y_max/y1_max:.2f}",
        fontsize=16,
    )
    ax.legend()
    plt.legend()
    fig.savefig(output_path("output_scalability_tps.jpg"))


def scalability_latency():
    data = Data()
    ncol = 1
    nrow = 1
    index = 0
    fig = plt.figure(figsize=(9, 9))
    fig.suptitle("Scalability")
    fig.tight_layout()
    plt.subplots_adjust(
        left=None, bottom=None, right=None, top=None, wspace=0.3, hspace=0.5
    )
    indicator = "latency_avg"
    ratio = 1.0
    x, y = getxy(indicator, data.rt_pn_tor[ratio])
    x1, y1 = getxy(indicator, data.rt_pn_aor[ratio])
    x2, y2 = getxy(indicator, data.rt_pn_nor[ratio])
    diffs = [[(a, a), (y[idx], y1[idx])] for idx, a in enumerate(x)]
    diffvals = [(i, (a + b) / 2, b / a) for i, a, b in zip(x, y, y1)]
    index += 1
    ax = plt.subplot(
        nrow,
        ncol,
        index,
    )
    ax.set_title(f"ratio={ratio}")
    ax.set_xlabel("paranum")
    ax.set_ylabel(indicator)
    # ax.set_ylim(ymin=10)
    ax.plot(x, y, label="ToR", marker="D")
    ax.plot(x1, y1, label="AoR", marker="s")
    ax.plot(x2, y2, label="NoR", marker="^")
    for x, y in diffs:
        ax.plot(x, y, linestyle="--", color="black")
    for x, y, val in diffvals:
        ax.text(x=x + 1, y=y, s=r"$\Delta $" + f"={val:.2f}", fontsize=16)
    ax.legend()
    plt.legend()
    fig.savefig(output_path("output_scalability_latency.jpg"))


def scalability_latency_tps():
    data = Data()
    ncol = 2
    nrow = 1
    index = 0
    fig = plt.figure(figsize=(18, 9))
    fig.suptitle("Scalability", fontsize=24)
    fig.tight_layout()
    plt.subplots_adjust(
        left=None, bottom=None, right=None, top=None, wspace=0.3, hspace=0.5
    )
    indicator = "latency_avg"
    ratio = 0.4
    x, y = getxy(indicator, data.rt_pn_tor[ratio])
    x1, y1 = getxy(indicator, data.rt_pn_aor[ratio])
    x2, y2 = getxy(indicator, data.rt_pn_nor[ratio])
    diffs = [[(a, a), (y[idx], y1[idx])] for idx, a in enumerate(x)]
    diffvals = [(i, (a + b) / 2, 1 - a / b) for i, a, b in zip(x, y, y1)]
    index += 1
    ax = plt.subplot(
        nrow,
        ncol,
        index,
    )
    ax.set_title(f"ratio={ratio}", fontsize=16)
    ax.set_xlabel("paranum", fontsize=16)
    ax.set_ylabel(indicator, fontsize=16)
    # ax.set_ylim(ymin=10)
    ax.plot(x, y, label="ToR", marker="D")
    ax.plot(x1, y1, label="AoR", marker="s")
    ax.plot(x2, y2, label="NoR", marker="^")
    for x, y in diffs:
        ax.plot(x, y, linestyle="--", color="black")
    for x, y, val in diffvals:
        ax.text(x=x + 1, y=y, s=r"$\Delta $" + f"={val:.2f}", fontsize=16)
    ax.legend(prop={"size": 12})

    indicator = "tps"
    ratio = 0.4
    x, y = getxy(indicator, data.rt_pn_tor[ratio])
    x1, y1 = getxy(indicator, data.rt_pn_aor[ratio])
    x2, y2 = getxy(indicator, data.rt_pn_nor[ratio])
    x_max, y_max = max(zip(range(len(y)), y), key=lambda a: a[1])
    x1_max, y1_max = max(zip(range(len(y1)), y1), key=lambda a: a[1])
    index += 1
    ax = plt.subplot(
        nrow,
        ncol,
        index,
    )
    ax.set_title(f"ratio={ratio}", fontsize=16)
    ax.set_xlabel("paranum", fontsize=16)
    ax.set_ylabel(indicator, fontsize=16)
    ax.set_ylim(ymax=300, ymin=0)
    ax.set_xlim(xmin=0, xmax=60)
    ax.plot(x, y, label="ToR", marker="D")
    ax.plot(x1, y1, label="AoR", marker="s")
    ax.plot(x2, y2, label="NoR", marker="^")
    ax.plot([0] + x[: x_max + 1], [y_max] * (x_max + 2), linestyle="--", color="black")
    ax.plot([x[x_max], x[x_max]], [0, y_max], linestyle="--", color="black")
    ax.text(x=x[x_max] + 1, y=y_max + 5, s=f"max={y_max:.2f}", fontsize=16)
    ax.plot(
        [0] + x1[: x1_max + 1], [y1_max] * (x1_max + 2), linestyle="--", color="black"
    )
    ax.plot([x1[x1_max], x1[x1_max]], [0, y1_max], linestyle="--", color="black")
    ax.text(x=x1[x1_max] + 1, y=y1_max + 5, s=f"max={y1_max:.2f}", fontsize=16)
    ax.text(
        x=x[x_max] + 1,
        y=(y_max + y1_max) / 2,
        s=r"$\Delta $" + f"={y_max/y1_max-1:.2f}",
        fontsize=16,
    )
    ax.legend(prop={"size": 12})

    fig.savefig(output_path("output_scalability_latency_tps.jpg"))


if __name__ == "__main__":
    total_latency()
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
    # inter_load_avg_simple()
    # inter_load_delta()
    # inter_load_max()
    # scalability_tps()
    # scalability_latency()
    scalability_latency_tps()

import os, sys
import json
from matplotlib import pyplot as plt

workloads_dir = "locals/workload_ratio_analysis/output/workloads"

average = lambda x: sum(x) / len(x)

result = {}
result_rev = {}
for filename in os.listdir(workloads_dir):
    mode, chainnum, gen_xtx_num = filename.split(".")[0].split("-")
    chainnum = int(chainnum)
    gen_xtx_num = int(gen_xtx_num)
    if result.get(chainnum, None) is None:
        result[chainnum] = {}
    if result[chainnum].get(gen_xtx_num, None) is None:
        result[chainnum][gen_xtx_num] = {}
    if result_rev.get(gen_xtx_num, None) is None:
        result_rev[gen_xtx_num] = {}
    if result_rev[gen_xtx_num].get(chainnum, None) is None:
        result_rev[gen_xtx_num][chainnum] = {}
    filepath = os.path.join(workloads_dir, filename)
    data = json.load(open(filepath, "r"))
    print(
        f"{filename}: {average(data['30000'])}, {average([len(v) for k,v in data.items() if k != '30000']):.2f}"
    )
    result[chainnum][gen_xtx_num][mode] = average(data["30000"])
    result_rev[gen_xtx_num][chainnum][mode] = average(data["30000"])

finalresult = []
for chainnum, item in result.items():
    for gen_xtx_num, item in item.items():
        if item.get("ToR", None) and item.get("AoR", None):
            ratio = 1 - item["ToR"] / item["AoR"]
            finalresult.append((chainnum, gen_xtx_num, ratio))

finalresult = sorted(finalresult, key=lambda x: (x[1], x[0]))
print(*finalresult, sep="\n")

ncol = 2
nrow = 2
index = 0
fig = plt.figure(figsize=(ncol * 3, nrow * 3))
fig.tight_layout()
plt.subplots_adjust(
    left=None, bottom=None, right=None, top=None, wspace=0.4, hspace=0.5
)

for gen_xtx_num in [5, 10, 15, 20]:
    theoretical_val = gen_xtx_num / (gen_xtx_num + 1)
    data = list(result_rev[gen_xtx_num].items())
    data = sorted(data, key=lambda x: x[0])
    x, y = zip(*data)
    y = [1 - item["ToR"] / item["AoR"] for item in y]

    index += 1
    ax = plt.subplot(
        nrow,
        ncol,
        index,
    )
    ax.set_title(r"$\overline{x}$=" + f"{gen_xtx_num}")
    ax.set_xlabel("parallel chain number")
    ax.set_ylabel(r"opt ratio: $\tau$")
    ax.set_ylim(ymin=theoretical_val - 0.01, ymax=1)
    ax.plot(x, y, marker="D")


    ax.axhline(y=theoretical_val, color="r", linestyle="dashed")
    ax.text(
        x=x[-1] / 4,
        y=theoretical_val + 0.005,
        s=r"LowerBound=" + f"{theoretical_val:.3f}",
    )

fig.savefig("locals/workload_ratio_analysis/plot/output_workload_optimization_ratio.jpg")

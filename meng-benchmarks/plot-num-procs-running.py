import matplotlib.pyplot as plt
import re
from datetime import datetime
import os

# Read file contents
file_path1 = os.path.expanduser("benchmarks/results/e2e-fttask-named-5/mr_vs_corral/e2e-mr-wiki20G-wc-ux-256.yml-warm/bench.out.0")
file_path2 = os.path.expanduser("benchmarks/results/e2e-fttask-server-2/mr_vs_corral/e2e-mr-wiki20G-wc-ux-256.yml-warm/bench.out.0")

with open(file_path1, "r") as f:
    dataset1 = f.read()

with open(file_path2, "r") as f:
    dataset2 = f.read()

def parse_data(lines):
    timestamps = []
    r_values = [[] for _ in range(9)]
    time_format = "%H:%M:%S.%f"
    base_time = None

    # First pass: find base_time
    for line in lines:
        if "BENCH Start MR job" in line:
            match = re.match(r"(\d{2}:\d{2}:\d{2}\.\d+)", line)
            if match:
                base_time = datetime.strptime(match.group(1), time_format)
                break
    if base_time is None:
        raise ValueError("Base time not found: no line contains 'BENCH Start MR job'.")

    # Second pass: parse actual data
    for line in lines:
        match = re.match(r"(\d{2}:\d{2}:\d{2}\.\d+)", line)
        if not match:
            continue
        timestamp = datetime.strptime(match.group(1), time_format)
        time_delta = (timestamp - base_time).total_seconds()

        r_matches = re.findall(r"\[ r:(\d+)", line)
        if len(r_matches) != 9:
            continue
        timestamps.append(time_delta)
        for i, r in enumerate(r_matches):
            r_values[i].append(int(r))

    return timestamps, r_values

# Parse data
t1, rsets1 = parse_data(dataset1.split("\n"))
t2, rsets2 = parse_data(dataset2.split("\n"))

# Find global min and max for y-axis
all_values = [v for rset in rsets1 + rsets2 for v in rset]
global_min = min(all_values)
global_max = max(all_values)
margin = 0.1 * (global_max - global_min)
ylim = (global_min - margin, global_max + margin)

# Plotting
fig, axs = plt.subplots(2, 1, figsize=(12, 8), sharex=True)

for i in range(9):
    axs[0].plot(t1, rsets1[i], label=f"Node {i}", marker='.')
    axs[1].plot(t2, rsets2[i], label=f"Node {i}", marker='.')

for ax in axs:
    ax.set_ylim(ylim)
    ax.legend(loc="upper right")
    ax.grid(True)

axs[0].set_title("Old ft/task")
axs[1].set_title("New ft/task")
axs[1].set_xlabel("Time since MR job started (s)")
axs[0].set_ylabel("# procs running")
axs[1].set_ylabel("# procs running")

plt.tight_layout()
plt.savefig("comparison_plot.png", dpi=300)

import os
import re
import statistics
from collections import defaultdict
import numpy as np
from scipy.stats import ttest_ind

# ANSI color codes
GREEN = "\033[92m"  # Green text
RED = "\033[91m"    # Red text
RESET = "\033[0m"   # Reset to default color

ROOT = "./benchmarks/results"
VERSIONS = ["fttask-server", "old-fttask"]
STATS = ["mean", "min", "max", "median", "stdev"]

# Match a line like "Mean: 1m56.476123771s" or "Mean: 2m5.337531432s"
DURATION_RE = re.compile(r"Mean:\s+((?:(\d+)m)?([\d.]+)s)")

# Match task types in lines like:
# [mr-r-wc-ryan-mr-wiki20G-wc-ux-128.yml-mr-a47-benchrealm1-aad2bbbdfccecb98, kid:sigma-node4-731]:
TASK_TYPE_RE = re.compile(r"\[(mr-([mr])-[^,\]]+)")

# Match inner timing in lines like:
#       in 502 MB out 38 MB tot 514.6996984481812 inner 14006ms outer 14478ms (36.75MB/s)
INNER_TIME_RE = re.compile(r"inner (\d+)ms")

MAP_PHASE_RE = re.compile(r"map phase took (\d+)ms")

def parse_duration(s):
    """Convert duration string like '1m56.476123771s' to float seconds."""
    match = DURATION_RE.search(s)
    if not match:
        return None
    minutes = int(match.group(2) or 0)
    seconds = float(match.group(3))
    return minutes * 60 + seconds

# { testname: { version: { 'overall': [list of durations], 'mapper': [list of durations], 'reducer': [list of durations] } } }
results = defaultdict(lambda: defaultdict(lambda: defaultdict(list)))

for dirname in os.listdir(ROOT):
    for version in VERSIONS:
        if dirname.startswith("reducer-" + version):
        # if dirname.startswith("10x-bin-" + version):
        # if dirname.startswith("mapper-only-" + version):
        # if dirname.startswith(version + "-1.6-benchmark"):
        # if dirname.startswith("60G-mapper-only-" + version):
            print(f"Processing {dirname} for {version}")
            testroot = os.path.join(ROOT, dirname, "mr_vs_corral")
            if not os.path.exists(testroot):
                continue
            for testname in os.listdir(testroot):
                print(f"  Test: {testname}")
                path = os.path.join(testroot, testname, "bench.out.0")
                if not os.path.exists(path):
                    print(f"  No file found at {path}")
                    continue
                
                with open(path) as f:
                    lines = f.readlines()
                    content = "".join(lines)
                    
                    # Extract overall benchmark time
                    overall_duration = parse_duration(content)
                    if overall_duration is not None:
                        results[testname][version]['overall'].append(overall_duration)
                    else:
                        print(f"  No overall duration found in {path}")
                    
                    # Process the file line by line to match task types with their inner times
                    mapper_times = []
                    reducer_times = []
                    current_task_type = None
                    
                    for i, line in enumerate(lines):
                        # Check if this is a task definition line
                        task_match = TASK_TYPE_RE.search(line)
                        if task_match:
                            current_task_type = task_match.group(2)  # 'm' or 'r'
                            continue
                            
                        # If we have a current task type and this line has inner time
                        if current_task_type and "inner" in line:
                            inner_match = INNER_TIME_RE.search(line)
                            if inner_match:
                                inner_time_ms = int(inner_match.group(1))
                                inner_time_s = inner_time_ms / 1000.0  # Convert to seconds
                                
                                if current_task_type == 'm':
                                    mapper_times.append(inner_time_s)
                                elif current_task_type == 'r':
                                    reducer_times.append(inner_time_s)
                                    
                                # Reset for next task
                                current_task_type = None
                    
                    if mapper_times:
                        # Store average mapper time for this run
                        avg_mapper_time = sum(mapper_times) / len(mapper_times)
                        results[testname][version]['mapper'].append(avg_mapper_time)
                        print(f"  Found {len(mapper_times)} mappers, avg time: {avg_mapper_time:.2f}s, std dev: {statistics.stdev(mapper_times):.2f}s, median: {statistics.median(mapper_times):.2f}s")
                    else:
                        print(f"  No mapper times found in {path}")
                        
                    if reducer_times:
                        # Store average reducer time for this run
                        avg_reducer_time = sum(reducer_times) / len(reducer_times)
                        results[testname][version]['reducer'].append(avg_reducer_time)
                        print(f"  Found {len(reducer_times)} reducers, avg time: {avg_reducer_time:.2f}s, std dev: {statistics.stdev(reducer_times):.2f}s, median: {statistics.median(reducer_times):.2f}s")
                    else:
                        print(f"  No reducer times found in {path}")

                    # Additional: Search sigmaos-node-logs for map phase times
                    logdir = os.path.join(testroot, testname, "sigmaos-node-logs")
                    map_phase_times = []

                    if os.path.exists(logdir):
                        for fname in os.listdir(logdir):
                            fpath = os.path.join(logdir, fname)
                            if not os.path.isfile(fpath):
                                continue
                            try:
                                with open(fpath) as f:
                                    for line in f:
                                        match = MAP_PHASE_RE.search(line)
                                        if match:
                                            ms = int(match.group(1))
                                            map_phase_times.append(ms / 1000.0)  # Convert ms to seconds
                            except Exception as e:
                                print(f"  Error reading {fpath}: {e}")

                        if map_phase_times:
                            avg_map_phase = sum(map_phase_times) / len(map_phase_times)
                            results[testname][version]['map_phase'].append(avg_map_phase)
                            print(f"  Found {len(map_phase_times)} 'map phase' entries, avg time: {avg_map_phase:.2f}s")
                        else:
                            print(f"  No 'map phase' times found in {logdir}")

# Function to print statistics for a data set
def print_stats(data, label):
    if not data:
        print(f"  {label}: No data available")
        return
        
    print(f"  {label}:")
    print(f"    Runs: {len(data)}")
    print(f"    mean     = {statistics.mean(data):.2f}s")
    print(f"    min      = {min(data):.2f}s")
    print(f"    max      = {max(data):.2f}s")
    print(f"    median   = {statistics.median(data):.2f}s")
    print(f"    stdev    = {statistics.stdev(data):.2f}s" if len(data) > 1 else "    stdev    = N/A")
    print(f"    all      = [{', '.join(f'{t:.2f}s' for t in sorted(data))}]")

def print_comparison_table(data1, data2, label, v1, v2):
    print(f"  {label}:")

    def format_val(fn, data):
        try:
            return f"{fn(data):.2f}s" if data else "N/A"
        except Exception as e:
            return f"N/A"

    stat_names = ["mean", "min", "max", "median", "stdev", "runs"]
    rows = []

    for stat in stat_names:
        if stat == "runs":
            val1 = str(len(data1)) if data1 else "0"
            val2 = str(len(data2)) if data2 else "0"
        else:
            fn = getattr(statistics, stat) if hasattr(statistics, stat) else None
            if fn:
                val1 = format_val(fn, data1) if len(data1) >= 1 else "N/A"
                val2 = format_val(fn, data2) if len(data2) >= 1 else "N/A"
            else:
                if stat == "min":
                    val1 = format_val(min, data1) if data1 else "N/A"
                    val2 = format_val(min, data2) if data2 else "N/A"
                elif stat == "max":
                    val1 = format_val(max, data1) if data1 else "N/A"
                    val2 = format_val(max, data2) if data2 else "N/A"
                else:
                    val1 = val2 = "N/A"
        rows.append((stat.capitalize(), val1, val2))

    col1_width = max(len(row[0]) for row in rows) + 2
    print(f"    {'Stat':<{col1_width}}{v1:<15}{v2}")
    for name, val1, val2 in rows:
        print(f"    {name:<{col1_width}}{val1:<15}{val2}")

# Function to perform t-test between two data sets
def perform_ttest(data1, data2, label1, label2):
    if len(data1) > 1 and len(data2) > 1:
        stat, pval = ttest_ind(data1, data2, equal_var=False)  # Welch's t-test
        
        # Calculate percentage difference
        mean1 = statistics.mean(data1)
        mean2 = statistics.mean(data2)
        if mean1 != 0 and mean2 != 0:
            pct_diff = ((mean2 - mean1) / mean1) * 100
            
            # Determine color based on p-value and performance
            # GREEN if statistically significant (p < 0.05) AND old-fttask is slower (positive pct_diff)
            # RED otherwise
            is_significant = pval < 0.05
            is_improvement = pct_diff > 0  # old-fttask is slower = improvement for fttask-server
            
            color = GREEN if (is_significant and is_improvement) else RED
            
            # Print t-test results with color
            print(f"  t-test between {label1} and {label2}:")
            print(f"    t-statistic = {stat:.4f}")
            
            # Color the p-value based on significance
            p_value_str = f"    p-value     = {color}{pval:.4f}{RESET}"
            print(p_value_str + (f" {color}(Significant!){RESET}" if is_significant else ""))
            
            # Color the percentage difference based on direction
            if pct_diff < 0:
                direction_msg = f"    {label2} is {RED}{abs(pct_diff):.2f}% faster{RESET} than {label1}"
            else:
                direction_msg = f"    {label2} is {GREEN}{pct_diff:.2f}% slower{RESET} than {label1}"
                
            print(direction_msg)
    else:
        print(f"  Not enough data for t-test between {label1} and {label2}")

# Process and print results
for testname in sorted(results.keys()):
    print(f"\n=== Test: {testname} ===")
    
    print(f"\n--- Summary Statistics ---")

    v1, v2 = VERSIONS
    for metric in ['overall', 'mapper', 'reducer', 'map_phase']:
        data1 = results[testname][v1][metric]
        data2 = results[testname][v2][metric]
        print_comparison_table(data1, data2, f"{metric.capitalize()} Time", v1, v2)
    
    # If we have exactly 2 versions with valid data, do the t-tests
    if len(results[testname]) == 2:
        v1, v2 = VERSIONS
        print("\n--- Statistical Comparison ---")
        
        # Perform t-tests for overall, mapper, and reducer times
        for metric in ['overall', 'mapper', 'reducer', 'map_phase']:
            data1 = results[testname][v1][metric]
            data2 = results[testname][v2][metric]
            
            if data1 and data2:
                print(f"\n{metric.capitalize()} Time Comparison:")
                perform_ttest(data1, data2, v1, v2)
            else:
                print(f"\n{metric.capitalize()} Time Comparison: Insufficient data")
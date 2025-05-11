import os
import re
import statistics
from collections import defaultdict
import numpy as np # Keeping as per original
from scipy.stats import ttest_ind
from datetime import datetime, timezone # Added for timestamp parsing

# ANSI color codes

GREEN = "\033[92m"  # Green text
RED = "\033[91m"    # Red text
RESET = "\033[0m"   # Reset to default color

ROOT = "./benchmarks/results"
VERSIONS = ["fttask-server", "fttask-named"]
STATS = ["mean", "min", "max", "median", "stdev"] # Keeping as per original

# Match a line like "Mean: 1m56.476123771s" or "Mean: 2m5.337531432s"

DURATION_RE = re.compile(r"Mean:\s+((?:(\d+)m)?([\d.]+)s)")

# Match task types in lines like:

# [mr-r-wc-ryan-mr-wiki20G-wc-ux-128.yml-mr-a47-benchrealm1-aad2bbbdfccecb98, kid\:sigma-node4-731]:

TASK_TYPE_RE = re.compile(r"(mr-([mr])-[^,$]+)")

# Match inner timing in lines like:

# in 502 MB out 38 MB tot 514.6996984481812 inner 14006ms outer 14478ms (36.75MB/s)

INNER_TIME_RE = re.compile(r"inner (\d+)ms")

MAP_PHASE_RE = re.compile(r"map phase took (\d+)ms")

# Regex to find lines with "prep to spawn proc mr-m" and capture timestamp.

# Example: "02:36:07.239267 mr-coord-... prep to spawn proc mr-m" -> captures "02:36:07.239267"

PREP_SPAWN_RE = re.compile(r"^(\S+)\s+.*prep to spawn proc mr-m")

# Regexes for MR Job Preparation duration from bench.out.0
# Example: "22:04:30.998712 ... TEST Prepare MR job ..."
PREPARE_MR_JOB_RE = re.compile(r"^(\S+)\s+.*?TEST Prepare MR job")
# Example: "22:04:31.933741 ... TEST Done prepare MR job ..."
DONE_PREPARE_MR_JOB_RE = re.compile(r"^(\S+)\s+.*?TEST Done prepare MR job")

# Regex for MR_COORD startTasks time, supporting ms or s
# Captures: 1. Line Timestamp, 2. Time Value, 3. Time Unit
# Example: "00:56:02.070011 mr-coord-... MR_COORD startTasks 683 time: 59.540758ms"
START_TASKS_TIME_RE = re.compile(r"^(\S+)\s+.*?MR_COORD startTasks \d+ time: ([\d.]+)(ms|s)")


def parse_duration(s):
    """Convert duration string like '1m56.476123771s' to float seconds."""
    match = DURATION_RE.search(s)
    if not match:
        return None
    minutes = int(match.group(2) or 0)
    seconds = float(match.group(3))
    return minutes * 60 + seconds

def parse_log_timestamp(ts_str):
    """
    Parses a timestamp string, primarily expecting HH:MM:SS.ffffff format.
    Returns a datetime object or None.
    """
    try:
        # This format matches "02:36:07.239267"
        return datetime.strptime(ts_str, "%H:%M:%S.%f")
    except ValueError:
        # Fallback for ISO8601 with Z, if encountered from other potential log sources
        try:
            if ts_str.endswith('Z'):
                return datetime.strptime(ts_str[:-1], "%Y-%m-%dT%H:%M:%S.%f").replace(tzinfo=timezone.utc)
        except ValueError:
            pass # Inner try failed
        # print(f"Warning: Could not parse timestamp: {ts_str}") # Uncomment for debugging
        return None

# { testname: { version: { 'metric_name': [list of values] } } }

results = defaultdict(lambda: defaultdict(lambda: defaultdict(list)))
METRICS_TO_REPORT = ['overall', 'mapper', 'reducer', 'map_phase', 'mr_m_spawn_prep_duration', 'mr_job_prep_duration', 'start_tasks_duration']

for dirname in os.listdir(ROOT):
    for version_from_list in VERSIONS:
        if dirname.startswith("mapper-only-" + version_from_list): # Make sure this prefix matches your directory names
            print(f"Processing {dirname} for {version_from_list}")
            testroot = os.path.join(ROOT, dirname, "mr_vs_corral")
            if not os.path.exists(testroot):
                continue
            for testname in os.listdir(testroot):
                print(f"  Test: {testname}")
                path = os.path.join(testroot, testname, "bench.out.0")
                if not os.path.exists(path):
                    print(f"    No bench.out.0 file found at {path}")
                    continue

                mapper_times_from_bench_out = []
                reducer_times_from_bench_out = []
                prepare_mr_job_ts_val = None
                done_prepare_mr_job_ts_val = None
                
                with open(path, 'r', encoding='utf-8', errors='ignore') as f:
                    lines = f.readlines()
                    content = "".join(lines)
                    
                    overall_duration = parse_duration(content)
                    if overall_duration is not None:
                        results[testname][version_from_list]['overall'].append(overall_duration)
                    else:
                        print(f"    No overall duration found in {path}")
                    
                    current_task_type = None
                    for i, line in enumerate(lines):
                        task_match = TASK_TYPE_RE.search(line)
                        if task_match:
                            current_task_type = task_match.group(2)
                            continue 
                            
                        if current_task_type and "inner" in line:
                            inner_match = INNER_TIME_RE.search(line)
                            if inner_match:
                                inner_time_ms = int(inner_match.group(1))
                                inner_time_s = inner_time_ms / 1000.0
                                
                                if current_task_type == 'm':
                                    mapper_times_from_bench_out.append(inner_time_s)
                                elif current_task_type == 'r':
                                    reducer_times_from_bench_out.append(inner_time_s)
                                current_task_type = None
                        
                        if prepare_mr_job_ts_val is None:
                            match_prepare = PREPARE_MR_JOB_RE.search(line)
                            if match_prepare:
                                ts_str = match_prepare.group(1)
                                parsed_ts = parse_log_timestamp(ts_str)
                                if parsed_ts:
                                    prepare_mr_job_ts_val = parsed_ts
                                else:
                                    print(f"    Warning: Could not parse 'Prepare MR job' timestamp '{ts_str}' in {path} from line: {line.strip()}")

                        if done_prepare_mr_job_ts_val is None:
                            match_done = DONE_PREPARE_MR_JOB_RE.search(line)
                            if match_done:
                                ts_str = match_done.group(1)
                                parsed_ts = parse_log_timestamp(ts_str)
                                if parsed_ts:
                                    done_prepare_mr_job_ts_val = parsed_ts
                                else:
                                    print(f"    Warning: Could not parse 'Done Prepare MR job' timestamp '{ts_str}' in {path} from line: {line.strip()}")

                if mapper_times_from_bench_out:
                    avg_mapper_time = sum(mapper_times_from_bench_out) / len(mapper_times_from_bench_out)
                    results[testname][version_from_list]['mapper'].append(avg_mapper_time)
                    stdev_str = f", std dev: {statistics.stdev(mapper_times_from_bench_out):.2f}s" if len(mapper_times_from_bench_out) > 1 else ""
                    median_str = f", median: {statistics.median(mapper_times_from_bench_out):.2f}s" if mapper_times_from_bench_out else ""
                    print(f"    Found {len(mapper_times_from_bench_out)} mappers (bench.out), avg time: {avg_mapper_time:.2f}s{stdev_str}{median_str}")
                else:
                    print(f"    No mapper times found in {path} for 'inner' time.")
                    
                if reducer_times_from_bench_out:
                    avg_reducer_time = sum(reducer_times_from_bench_out) / len(reducer_times_from_bench_out)
                    results[testname][version_from_list]['reducer'].append(avg_reducer_time)
                    stdev_str = f", std dev: {statistics.stdev(reducer_times_from_bench_out):.2f}s" if len(reducer_times_from_bench_out) > 1 else ""
                    median_str = f", median: {statistics.median(reducer_times_from_bench_out):.2f}s" if reducer_times_from_bench_out else ""
                    print(f"    Found {len(reducer_times_from_bench_out)} reducers (bench.out), avg time: {avg_reducer_time:.2f}s{stdev_str}{median_str}")
                else:
                    print(f"    No reducer times found in {path} for 'inner' time.")

                if prepare_mr_job_ts_val and done_prepare_mr_job_ts_val:
                    if done_prepare_mr_job_ts_val >= prepare_mr_job_ts_val:
                        mr_job_prep_duration_s = (done_prepare_mr_job_ts_val - prepare_mr_job_ts_val).total_seconds()
                        results[testname][version_from_list]['mr_job_prep_duration'].append(mr_job_prep_duration_s)
                        print(f"    Found MR Job Prep duration (bench.out): {mr_job_prep_duration_s:.3f}s")
                    else:
                        print(f"    Warning: 'Done Prepare MR job' timestamp ({done_prepare_mr_job_ts_val}) is before 'Prepare MR job' timestamp ({prepare_mr_job_ts_val}) in {path}. Skipping this metric for this file.")
                elif prepare_mr_job_ts_val and not done_prepare_mr_job_ts_val:
                    print(f"    Found 'TEST Prepare MR job' but no 'TEST Done prepare MR job' in {path} for MR Job Prep duration calculation.")
                elif not prepare_mr_job_ts_val and done_prepare_mr_job_ts_val:
                     print(f"    Found 'TEST Done prepare MR job' but no 'TEST Prepare MR job' in {path} for MR Job Prep duration calculation.")
                else:
                    print(f"    No 'TEST Prepare MR job' / 'TEST Done prepare MR job' pair found in {path} for MR Job Prep duration calculation.")


                logdir = os.path.join(testroot, testname, "sigmaos-node-logs")
                map_phase_times_current_run = []
                prep_spawn_durations_current_run = []
                
                # Variables to find the chronologically first startTasks event in this run
                first_start_task_timestamp_for_run = None
                first_start_task_duration_s_for_run = None

                if os.path.exists(logdir):
                    for fname in os.listdir(logdir):
                        fpath = os.path.join(logdir, fname)
                        if not os.path.isfile(fpath):
                            continue
                        
                        current_file_prep_spawn_timestamps = []
                        try:
                            with open(fpath, 'r', encoding='utf-8', errors='ignore') as f_log:
                                for line in f_log:
                                    match_map_phase = MAP_PHASE_RE.search(line)
                                    if match_map_phase:
                                        ms = int(match_map_phase.group(1))
                                        map_phase_times_current_run.append(ms / 1000.0)
                                    
                                    match_prep_spawn = PREP_SPAWN_RE.search(line)
                                    if match_prep_spawn:
                                        timestamp_str = match_prep_spawn.group(1)
                                        dt_obj = parse_log_timestamp(timestamp_str)
                                        if dt_obj:
                                            current_file_prep_spawn_timestamps.append(dt_obj)
                                    
                                    match_start_tasks = START_TASKS_TIME_RE.search(line)
                                    if match_start_tasks:
                                        line_timestamp_str = match_start_tasks.group(1)
                                        time_val_str = match_start_tasks.group(2)
                                        time_unit = match_start_tasks.group(3).lower()
                                        
                                        current_line_dt = parse_log_timestamp(line_timestamp_str)
                                        if not current_line_dt:
                                            print(f"    Warning: Could not parse line timestamp '{line_timestamp_str}' for startTasks in {fpath} from line: {line.strip()}")
                                            continue

                                        try:
                                            time_val = float(time_val_str)
                                            current_duration_s = 0
                                            if time_unit == 'ms':
                                                current_duration_s = time_val / 1000.0
                                            elif time_unit == 's':
                                                current_duration_s = time_val
                                            else:
                                                print(f"    Warning: Unknown time unit '{time_unit}' for startTasks time in {fpath} from line: {line.strip()}")
                                                continue
                                            
                                            # Check if this is the first startTasks event or earlier than the current earliest
                                            if first_start_task_timestamp_for_run is None or current_line_dt < first_start_task_timestamp_for_run:
                                                first_start_task_timestamp_for_run = current_line_dt
                                                first_start_task_duration_s_for_run = current_duration_s
                                                # Optional debug:
                                                # print(f"      DEBUG_STASKS_FIRST: New earliest in {fpath.split('/')[-1]} at {line_timestamp_str}, duration {current_duration_s:.6f}s")

                                        except ValueError:
                                            print(f"    Warning: Could not parse startTasks time value '{time_val_str}' to float in {fpath} from line: {line.strip()}")

                        except Exception as e:
                            print(f"    Error reading {fpath}: {e}")

                        if len(current_file_prep_spawn_timestamps) >= 2:
                            min_ts = min(current_file_prep_spawn_timestamps)
                            max_ts = max(current_file_prep_spawn_timestamps)
                            duration_seconds = (max_ts - min_ts).total_seconds()
                            if duration_seconds >= 0:
                                prep_spawn_durations_current_run.append(duration_seconds)

                    # After processing all files in logdir for the current run:
                    if map_phase_times_current_run:
                        avg_map_phase = sum(map_phase_times_current_run) / len(map_phase_times_current_run)
                        results[testname][version_from_list]['map_phase'].append(avg_map_phase)
                        print(f"    Found {len(map_phase_times_current_run)} 'map phase' entries (logs), avg time: {avg_map_phase:.3f}s")
                    else:
                        print(f"    No 'map phase' times found in logs in {logdir}")

                    if prep_spawn_durations_current_run:
                        avg_prep_spawn_duration_s = sum(prep_spawn_durations_current_run) / len(prep_spawn_durations_current_run)
                        results[testname][version_from_list]['mr_m_spawn_prep_duration'].append(avg_prep_spawn_duration_s)
                        avg_prep_spawn_duration_us = avg_prep_spawn_duration_s * 1_000_000
                        print(f"    Found {len(prep_spawn_durations_current_run)} 'prep to spawn proc mr-m' durations (logs), avg: {avg_prep_spawn_duration_us:.0f}µs")
                    else:
                        print(f"    No 'prep to spawn proc mr-m' durations found in logs for {logdir}")

                    if first_start_task_duration_s_for_run is not None:
                        results[testname][version_from_list]['start_tasks_duration'].append(first_start_task_duration_s_for_run)
                        print(f"    Found first 'startTasks time' (logs) at {first_start_task_timestamp_for_run.strftime('%H:%M:%S.%f') if first_start_task_timestamp_for_run else 'N/A'}, duration: {first_start_task_duration_s_for_run:.3f}s")
                    else:
                        print(f"    No 'startTasks time' entries found in logs for {logdir}")
                else:
                     print(f"  Log directory {logdir} not found.")

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


def print_comparison_table(data1, data2, label, v1, v2, metric_key):
    print(f"  {label}:")
    def format_val(fn, data, key_for_format):
        try:
            if not data: return "N/A"
            if fn == statistics.stdev and len(data) < 2: return "N/A"
            
            val = fn(data)
            if key_for_format == 'mr_m_spawn_prep_duration':
                return f"{val * 1_000_000:.0f}µs"
            else: 
                return f"{val:.3f}s"
        except Exception:
            return "N/A"

    stat_names = ["mean", "min", "max", "median", "stdev", "runs"]
    rows = []

    for stat_str in stat_names:
        val1, val2 = "N/A", "N/A"
        if stat_str == "runs":
            val1 = str(len(data1)) if data1 else "0"
            val2 = str(len(data2)) if data2 else "0"
        else:
            fn = None
            if hasattr(statistics, stat_str): fn = getattr(statistics, stat_str)
            elif stat_str == "min": fn = min
            elif stat_str == "max": fn = max

            if fn:
                val1 = format_val(fn, data1, metric_key)
                val2 = format_val(fn, data2, metric_key)
        rows.append((stat_str.capitalize(), val1, val2))

    col1_width = max(len(row[0]) for row in rows) + 2 if rows else 6
    col2_width = max(15, len(v1) + 2) if rows else 15
    max_val2_len = 0
    if rows:
        max_val2_len = max(len(row[2]) for row in rows)
    col3_width = max(max(15, len(v2) + 2), max_val2_len) if rows else 15


    print(f"    {'Stat':<{col1_width}}{v1:<{col2_width}}{v2:<{col3_width}}")
    for name, v1_val, v2_val in rows:
        print(f"    {name:<{col1_width}}{v1_val:<{col2_width}}{v2_val:<{col3_width}}")


def perform_ttest(data1, data2, label1, label2, metric_key):
    if len(data1) < 2 or len(data2) < 2:
        return
    try:
        mean1_val = statistics.mean(data1)
        mean2_val = statistics.mean(data2)
    except statistics.StatisticsError: # Handle case where data might be empty after all, though guarded by len checks
        print(f"  t-test between {label1} and {label2}: Could not compute means (empty data).")
        return

    stat, pval = ttest_ind(data1, data2, equal_var=False, nan_policy='omit') # omit nans if any somehow get in

    pct_diff = 0
    if mean1_val != 0:
        pct_diff = ((mean2_val - mean1_val) / mean1_val) * 100
    elif mean2_val != 0:
        pct_diff = float('inf') if mean2_val > 0 else float('-inf')

    is_significant = pval < 0.05
    
    color = RESET
    if is_significant:
        if mean2_val < mean1_val: 
            color = GREEN 
        elif mean2_val > mean1_val: 
            color = RED 

    print(f"  t-test between {label1} and {label2}:")
    print(f"    t-statistic = {stat:.4f}")

    p_value_str = f"    p-value     = {color}{pval:.4f}{RESET}"
    print(p_value_str + (f" {color}(Significant!){RESET}" if is_significant else ""))

    mean1_display, mean2_display = "", ""
    if metric_key == 'mr_m_spawn_prep_duration':
        mean1_display = f"{mean1_val * 1_000_000:.0f}µs"
        mean2_display = f"{mean2_val * 1_000_000:.0f}µs"
    else: 
        mean1_display = f"{mean1_val:.3f}s"
        mean2_display = f"{mean2_val:.3f}s"

    if mean1_val == mean2_val:
         direction_msg = f"    Means are identical: {label1} {mean1_display}, {label2} {mean2_display}"
    elif mean1_val == 0 and mean2_val == 0 : # Both zero
         direction_msg = f"    Means are identical (both 0): {label1} {mean1_display}, {label2} {mean2_display}"
    elif mean1_val == 0:
        direction_msg = f"    {label1} is {mean1_display}, {label2} is {mean2_display}"
    elif mean2_val == 0:
        direction_msg = f"    {label1} is {mean1_display}, {label2} is {mean2_display} ({GREEN}infinitely faster{RESET} than {label1} if 0 is better)"
    elif pct_diff < 0:
        direction_msg = f"    {label2} is {GREEN}{abs(pct_diff):.2f}% faster{RESET} than {label1} (means: {label1} {mean1_display}, {label2} {mean2_display})"
    else:
        direction_msg = f"    {label2} is {RED}{pct_diff:.2f}% slower{RESET} than {label1} (means: {label1} {mean1_display}, {label2} {mean2_display})"
            
    print(direction_msg)


# Process and print results

for testname in sorted(results.keys()):
    print(f"\n=== Test: {testname} ===")
    print(f"\n--- Summary Statistics ---")
    v1_name, v2_name = VERSIONS[0], VERSIONS[1]

    for metric_key in METRICS_TO_REPORT:
        data1 = results[testname].get(v1_name, {}).get(metric_key, [])
        data2 = results[testname].get(v2_name, {}).get(metric_key, [])
        
        if data1 or data2:
            metric_display_name = metric_key.replace('_', ' ').capitalize()
            print_comparison_table(data1, data2, f"{metric_display_name} Time", v1_name, v2_name, metric_key)

    if v1_name in results[testname] and v2_name in results[testname]:
        print("\n--- Statistical Comparison ---")
        
        for metric_key in METRICS_TO_REPORT:
            data1 = results[testname][v1_name].get(metric_key, [])
            data2 = results[testname][v2_name].get(metric_key, [])
            
            if len(data1) > 0 and len(data2) > 0 : # Perform t-test only if data exists for both versions
                metric_display_name = metric_key.replace('_', ' ').capitalize()
                print(f"\n{metric_display_name} Time Comparison:")
                perform_ttest(data1, data2, v1_name, v2_name, metric_key)
            elif data1 or data2: # Data for one version but not both
                 metric_display_name = metric_key.replace('_', ' ').capitalize()
                 print(f"\n{metric_display_name} Time Comparison: Insufficient data for t-test (need data for both versions: {v1_name} has {len(data1)} runs, {v2_name} has {len(data2)} runs)")
    else:
        print("\n--- Statistical Comparison ---")
        print(f"  Insufficient data: one or both versions ({v1_name}, {v2_name}) missing for test '{testname}'. Skipping t-tests.")
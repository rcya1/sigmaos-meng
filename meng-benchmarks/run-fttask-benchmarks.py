import subprocess
import os
import sys
import re

def run(cmd, check=True, shell=False):
    print(f">>> {cmd}")
    return subprocess.run(cmd, shell=shell, check=check)

def run_benchmark(branch, iteration, app, name):
    try:
        run(["sudo", "pkill", "-f", "sigmaos"], check=False)

        filepath = "./benchmarks/remote/remote_test.go"
        with open(filepath, "r") as f:
            lines = f.readlines()

        lines[277] = re.sub(r'"[^"]*"', f'"{app}"', lines[277])

        with open(filepath, "w") as f:
            f.writelines(lines)

        # Clean and run tests
        run(["go", "clean", "-testcache"])
        result = run([
            "go", "test", "-v", "-timeout", "1h", "sigmaos/benchmarks/remote",
            "--run", "TestMR",
            "--parallelize",
            "--platform", "cloudlab",
            "--vpc", "none",
            "--tag", "rychang",
            "--no-shutdown",
            "--version", f"{name}-{branch}-{iteration}",
            "--branch", branch
        ], check=False)

        if result.returncode != 0:
            print(f"Test failed for branch {branch}, version {name}-{branch}-{iteration}")
            os.chdir("cloudlab")
            run(["./collect-results.sh"])
            os.chdir("..")

    except Exception as e:
        print(f"Error during benchmark: {e}")

subprocess.run(["sudo", "pkill", "-f", "sigmaos"], check=False)

branches = ["fttask-server", "old-fttask"]
base_dir = "./apps/mr/job-descriptions"
benchmark_names = [
    "e2e",
    "e2e-reducer",
    "10x-bin",
    "mapper-only"
]
benchmarks = {}

for entry in os.listdir(base_dir):
    for bench in benchmark_names:
        if not entry.startswith(bench):
            continue

        if bench not in benchmarks:
            benchmarks[bench] = []
        benchmarks[bench].append(entry)

for i in range(1):
    for branch in branches:
        # run(["git", "checkout", branch])
        # run(["./build.sh", "--parallel", "--target", "remote", "--push", "rychang"])
        for bench, apps in benchmarks.items():
            for app in apps:
                if bench == "mapper-only" and "300" in app:
                    lines_copy = []
                    with open("./cloudlab/start-sigmaos.sh", "r") as f:
                        lines = f.readlines()
                    lines[257] = "# " + lines[257]
                    lines[258] = "# " + lines[258]

                    with open("./cloudlab/start-sigmaos.sh", "w") as f:
                        f.writelines(lines)
                else:
                    lines_copy = []
                    with open("./cloudlab/start-sigmaos.sh", "r") as f:
                        lines = f.readlines()
                        lines_copy = [line for line in lines]
                    if lines[257].startswith("# "):
                        lines[257] = lines[257][2:]
                    if lines[258].startswith("# "):
                        lines[258] = lines[258][2:]

                    with open("./cloudlab/start-sigmaos.sh", "w") as f:
                        f.writelines(lines)

                run_benchmark(branch, i, os.path.join(bench, app), bench)


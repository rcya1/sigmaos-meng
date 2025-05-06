#!/bin/bash

# set -e

pkill -f sigmaos || true
cd cloudlab
./stop-sigmaos.sh --parallel || true
cd ..

run_benchmark() {
    local branch=$1
    local version=$2
    local bench=$3

    sudo pkill -f sigmaos || true
    sed -i "283s|.*|			{\"$bench\", 10, 4, 7000},|" ./benchmarks/remote/remote_test.go

    go clean -testcache
    go test -v -timeout 1h sigmaos/benchmarks/remote \
        --run TestMR \
        --parallelize \
        --platform cloudlab \
        --vpc none \
        --tag rychang \
        --no-shutdown \
        --version "2x150G-${branch}-${version}" \
        --branch "$branch" 2>&1

    if [ $? -ne 0 ]; then
        echo "Test failed for branch $branch, version $version, benchmark $bench. Collecting results..."
        cd cloudlab
        ./collect-results.sh
        cd ..
    fi
}

# branches=("fttask-server")
branches=("fttask-server" "old-fttask")
benchmarks=(
    # "ryan-mr-wiki20G-wc-ux-512.yml"
    # "ryan-mr-wiki20G-wc-ux-128-45.yml"
    # "ryan-mr-wiki20G-wc-ux-32-45.yml"
    # "ryan-mr-wiki20G-wc-ux-24-45.yml"
    "ryan-mr-wiki2G-wc-ux-10-45.yml"
    # "ryan-mr-wiki20G-wc-ux-32-135.yml"
    # "ryan-mr-wiki20G-wc-ux-32-225.yml"
    # "ryan-mr-wiki20G-wc-ux-16-45.yml"
)

for i in {1..10}; do
    for branch in "${branches[@]}"; do
        git checkout "$branch"
        ./build.sh --parallel --target remote --push rychang
        for bench in "${benchmarks[@]}"; do
            # if [[ "$branch" == "old-fttask" && ("$bench" == *"-16-45.yml" || "$bench" == *"-10-45.yml") ]]; then
            #     echo "Skipping $bench on $branch"
            #     continue
            # fi
            run_benchmark "$branch" "$i" "$bench"
        done
    done
done

#!/bin/bash

# set -e

pkill -f sigmaos || true
cd cloudlab
./stop-sigmaos.sh --parallel || true
cd ..

run_benchmark() {
    local branch=$1
    local iteration=$2
    local app=$3
    local name=$4

    sudo pkill -f sigmaos || true
    sed -i "283s|.*|			{\"$app\", 10, 4, 7000},|" ./benchmarks/remote/remote_test.go

    go clean -testcache
    go test -v -timeout 1h sigmaos/benchmarks/remote \
        --run TestMR \
        --parallelize \
        --platform cloudlab \
        --vpc none \
        --tag rychang \
        --no-shutdown \
        --version "${name}-${branch}-${iteration}" \J
        --branch "$branch" 2>&1

    if [ $? -ne 0 ]; then
        echo "Test failed for branch $branch, version $version, benchmark $bench. Collecting results..."
        cd cloudlab
        ./collect-results.sh
        cd ..
    fi
}

branches=("fttask-server" "old-fttask")
benchmarks=(
    "ryan-mr-wiki2G-wc-ux-10-45.yml"
)

for i in {1..10}; do
    for branch in "${branches[@]}"; do
        git checkout "$branch"
        ./build.sh --parallel --target remote --push rychang
        for bench in "${benchmarks[@]}"; do
            run_benchmark "$branch" "$i" "$bench"
        done
    done
done

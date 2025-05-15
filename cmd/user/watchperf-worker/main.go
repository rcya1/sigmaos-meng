package main

import (
	"math"
	"os"
	"runtime/debug"

	db "sigmaos/debug"
	"sigmaos/proc"
	drtest "sigmaos/sigmaclnt/fslib/dirreader/test"
	"sigmaos/util/perf"
)

func main() {
	if len(os.Args) < 8 {
		db.DFatalf("Usage: %v id ntrials watchdir responsedir tempdir oldornew measuremode\n", os.Args[0])
	}

	debug.SetGCPercent(-1) // disable GC
	debug.SetMemoryLimit(math.MaxInt64)

	p, err := perf.NewPerf(proc.GetProcEnv(), "WATCH_PERF_WORKER")
	if err != nil {
		db.DFatalf("%v: err %v", os.Args[0], err)
	}
	defer p.Done()

	w, err := drtest.NewPerfWorker(os.Args[1:])
	if err != nil {
		db.DFatalf("%v: err %v", os.Args[0], err)
	}

	w.Run()
}


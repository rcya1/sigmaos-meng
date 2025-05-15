package main

import (
	"math"
	"os"
	"runtime/debug"

	db "sigmaos/debug"
	"sigmaos/namesrv"
)

func main() {
	debug.SetGCPercent(-1) // disable GC
	debug.SetMemoryLimit(math.MaxInt64)

	if err := namesrv.Run(os.Args); err != nil {
		db.DFatalf("%v: err %v\n", os.Args[0], err)
	}
}

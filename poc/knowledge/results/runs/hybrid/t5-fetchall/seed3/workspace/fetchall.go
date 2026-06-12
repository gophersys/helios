package fetchall

import (
	"context"
	"errors"
	"sync"
)

// Result holds the output from a single input after processing.
type Result struct {
	Index  int
	Output string
}

// Process runs operation on each input with bounded concurrency.
// At most concurrency operations run simultaneously.
// Results are returned ordered by Index, containing only successful outputs.
// Errors are aggregated via errors.Join, preserving individual error reachability.
func Process(
	ctx context.Context,
	inputs []string,
	concurrency int,
	operation func(ctx context.Context, input string) (string, error),
) ([]Result, error) {
	if concurrency < 1 {
		return nil, errors.New("fetchall: concurrency must be at least 1")
	}
	if len(inputs) == 0 {
		return nil, nil
	}

	type entry struct {
		output string
		err    error
	}

	results := make([]entry, len(inputs))
	work := make(chan int, len(inputs))
	for i := range inputs {
		work <- i
	}
	close(work)

	var wg sync.WaitGroup
	for range concurrency {
		wg.Go(func() {
			for idx := range work {
				out, err := operation(ctx, inputs[idx])
				results[idx] = entry{out, err}
			}
		})
	}
	wg.Wait()

	var out []Result
	var errs []error
	for i, r := range results {
		if r.err != nil {
			errs = append(errs, r.err)
		} else {
			out = append(out, Result{Index: i, Output: r.output})
		}
	}

	if len(errs) > 0 {
		return out, errors.Join(errs...)
	}
	return out, nil
}
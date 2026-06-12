package fetchall

import (
	"context"
	"errors"
	"sync"
)

// Result holds one successfully processed input's output.
type Result struct {
	Index  int    // position of the input that produced this output
	Output string
}

// Process runs operation on each input with at most concurrency in-flight
// operations. Results are returned ordered by Index ascending. On failure it
// still runs every operation and aggregates every individual error so that
// each remains reachable via errors.Is / errors.As.
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

	sem := make(chan struct{}, concurrency)
	outputs := make([]string, len(inputs))
	errs := make([]error, len(inputs))

	var wg sync.WaitGroup
	for i, input := range inputs {
		i, input := i, input
		sem <- struct{}{} // acquire — blocks when at capacity
		wg.Go(func() {
			defer func() { <-sem }() // release
			out, err := operation(ctx, input)
			outputs[i] = out
			errs[i] = err
		})
	}
	wg.Wait()

	var results []Result
	var joined error
	for i := range outputs {
		if errs[i] != nil {
			joined = errors.Join(joined, errs[i])
		} else {
			results = append(results, Result{Index: i, Output: outputs[i]})
		}
	}
	return results, joined
}
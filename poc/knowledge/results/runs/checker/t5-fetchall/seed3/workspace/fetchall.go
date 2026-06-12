package fetchall

import (
	"context"
	"errors"
	"sync"
)

// Result holds a single processed output paired with its input index.
type Result struct {
	Index  int
	Output string
}

// Process runs operation concurrently over inputs, bounding concurrency to at
// most the given limit. Results are returned in input order (by Index
// ascending) and contain only successful outputs. When one or more operations
// fail, Process still runs every input and returns the partial results
// together with an aggregated error where each individual failure remains
// reachable via errors.Is / errors.As.
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

	type workResult struct {
		index  int
		output string
		err    error
	}

	results := make([]workResult, len(inputs))
	sem := make(chan struct{}, concurrency)
	var wg sync.WaitGroup

	for i, input := range inputs {
		// Acquire a semaphore slot, blocking until one is available.
		// This bounds the number of in-flight operations to concurrency.
		sem <- struct{}{}

		idx, inp := i, input
		wg.Go(func() {
			defer func() { <-sem }()

			out, err := operation(ctx, inp)
			results[idx] = workResult{index: idx, output: out, err: err}
		})
	}

	wg.Wait()

	var successful []Result
	var errs []error
	for _, r := range results {
		if r.err != nil {
			errs = append(errs, r.err)
		} else {
			successful = append(successful, Result{Index: r.index, Output: r.output})
		}
	}
	if len(errs) > 0 {
		return successful, errors.Join(errs...)
	}
	return successful, nil
}

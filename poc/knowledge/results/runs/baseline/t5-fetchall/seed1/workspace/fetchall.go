package fetchall

import (
	"context"
	"errors"
	"fmt"
	"sort"
	"sync"
)

// Result holds the output of a single successful operation, keyed by the
// position of its input in the original slice.
type Result struct {
	Index  int
	Output string
}

// Process runs operation concurrently for every input, bounding concurrency
// to the given limit. Results are returned in input order, with only
// successful entries present. When operations fail, all are still dispatched
// and the aggregate error preserves every individual failure reachable via
// errors.Is / errors.As.
func Process(
	ctx context.Context,
	inputs []string,
	concurrency int,
	operation func(ctx context.Context, input string) (string, error),
) ([]Result, error) {
	if concurrency < 1 {
		return nil, fmt.Errorf("fetchall: concurrency must be at least 1, got %d", concurrency)
	}
	if len(inputs) == 0 {
		return nil, nil
	}

	type job struct {
		index int
		input string
	}

	type jobResult struct {
		index  int
		output string
		err    error
	}

	numWorkers := concurrency
	if len(inputs) < numWorkers {
		numWorkers = len(inputs)
	}

	jobs := make(chan job, len(inputs))
	results := make(chan jobResult, len(inputs))

	for i, input := range inputs {
		jobs <- job{index: i, input: input}
	}
	close(jobs)

	var wg sync.WaitGroup
	for w := 0; w < numWorkers; w++ {
		wg.Add(1)
		go func() {
			defer wg.Done()
			for j := range jobs {
				out, err := operation(ctx, j.input)
				results <- jobResult{index: j.index, output: out, err: err}
			}
		}()
	}

	go func() {
		wg.Wait()
		close(results)
	}()

	var successes []Result
	var errs []error

	for r := range results {
		if r.err != nil {
			errs = append(errs, fmt.Errorf("fetchall: input %d: %w", r.index, r.err))
		} else {
			successes = append(successes, Result{Index: r.index, Output: r.output})
		}
	}

	sort.Slice(successes, func(i, j int) bool {
		return successes[i].Index < successes[j].Index
	})

	if len(errs) > 0 {
		return successes, errors.Join(errs...)
	}

	return successes, nil
}
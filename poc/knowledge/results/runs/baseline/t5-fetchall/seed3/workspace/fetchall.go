package fetchall

import (
	"context"
	"errors"
	"sort"
	"sync"
)

// Result pairs a processed output with its original input index.
type Result struct {
	Index  int
	Output string
}

// Process runs operation on every input string with at most concurrency
// operations in flight. Results are returned ordered by input position.
// Errors are collected and returned as a single aggregated error where
// every individual failure is reachable via errors.Is/errors.As.
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

	type workItem struct {
		input string
		index int
	}

	work := make(chan workItem)
	results := make(chan Result, len(inputs))
	errs := make(chan error, len(inputs))

	var wg sync.WaitGroup
	for i := 0; i < concurrency; i++ {
		wg.Add(1)
		go func() {
			defer wg.Done()
			for wi := range work {
				out, err := operation(ctx, wi.input)
				if err != nil {
					errs <- err
				} else {
					results <- Result{Index: wi.index, Output: out}
				}
			}
		}()
	}

	// Dispatch all work.
	for i, input := range inputs {
		work <- workItem{input: input, index: i}
	}
	close(work)

	wg.Wait()
	close(results)
	close(errs)

	// Collect and sort successful results.
	sorted := make([]Result, 0, len(inputs))
	for r := range results {
		sorted = append(sorted, r)
	}
	sort.Slice(sorted, func(i, j int) bool {
		return sorted[i].Index < sorted[j].Index
	})

	// Collect errors.
	var all []error
	for e := range errs {
		all = append(all, e)
	}

	if len(all) > 0 {
		return sorted, errors.Join(all...)
	}
	return sorted, nil
}

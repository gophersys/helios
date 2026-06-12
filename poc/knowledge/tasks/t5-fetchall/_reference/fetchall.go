// Package fetchall is the reference implementation used to validate the
// held-out verify suite. It is never shown to the agent.
package fetchall

import (
	"context"
	"errors"
	"fmt"
	"sort"
	"sync"
)

type Result struct {
	Index  int
	Output string
}

func Process(
	ctx context.Context,
	inputs []string,
	concurrency int,
	operation func(ctx context.Context, input string) (string, error),
) ([]Result, error) {
	if concurrency < 1 {
		return nil, errors.New("fetchall: concurrency must be >= 1")
	}
	if len(inputs) == 0 {
		return nil, nil
	}

	var (
		mu       sync.Mutex
		results  []Result
		failures = make([]error, len(inputs))
	)
	semaphore := make(chan struct{}, concurrency)
	var wg sync.WaitGroup
	for index, input := range inputs {
		wg.Go(func() {
			semaphore <- struct{}{}
			defer func() { <-semaphore }()
			output, err := operation(ctx, input)
			mu.Lock()
			defer mu.Unlock()
			if err != nil {
				failures[index] = fmt.Errorf("fetchall: input %d (%q): %w", index, input, err)
				return
			}
			results = append(results, Result{Index: index, Output: output})
		})
	}
	wg.Wait()

	sort.Slice(results, func(i, j int) bool { return results[i].Index < results[j].Index })
	if err := errors.Join(failures...); err != nil {
		return results, err
	}
	return results, nil
}

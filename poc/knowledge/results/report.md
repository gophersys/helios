# Knowledge-library POC — experiment report

Model: `openrouter/deepseek/deepseek-v4-flash` · Harness: omp non-interactive · Scoring: clean-room held-out tests + deterministic rule oracles

## Arms

| arm | runs | functional pass | tempted-rule violations/run | mean out-tokens | ±sd | mean turns | mean s/run | total cost $ | timeouts |
|---|---|---|---|---|---|---|---|---|---|
| baseline | 18 | 94% | 0.67 | 9799 | 8926 | 16.3 | 138 | 0.4428 | 0 |
| checker | 18 | 94% | 0.06 | 11329 | 5666 | 24.1 | 173 | 0.6243 | 0 |
| hybrid | 16 | 100% | 0.00 | 10252 | 4365 | 21.2 | 208 | 0.5188 | 0 |
| monolithic | 18 | 100% | 0.11 | 9044 | 4707 | 17.7 | 146 | 0.4482 | 0 |

## Rule × arm violation rates (over applicable runs)

| rule | baseline | checker | hybrid | monolithic |
|---|---|---|---|---|
| go/benchmark-loop | 3/3 (100%) | 0/3 (0%) | 0/3 (0%) | 0/3 (0%) |
| go/constructor-purity | 0/8 (0%) | 0/8 (0%) | 0/7 (0%) | 0/9 (0%) |
| go/context-first | 0/8 (0%) | 0/9 (0%) | 0/8 (0%) | 0/9 (0%) |
| go/environment-confinement | 0/3 (0%) | 0/3 (0%) | 0/3 (0%) | 0/3 (0%) |
| go/error-wrapping | 0/9 (0%) | 0/9 (0%) | 0/8 (0%) | 0/9 (0%) |
| go/errors-astype | 3/3 (100%) | 0/3 (0%) | 0/2 (0%) | 0/3 (0%) |
| go/interface-size | 0/8 (0%) | 0/8 (0%) | 0/8 (0%) | 0/9 (0%) |
| go/return-concrete | 0/8 (0%) | 0/8 (0%) | 0/8 (0%) | 0/9 (0%) |
| go/slog-multihandler | 3/3 (100%) | 0/2 (0%) | 0/2 (0%) | 0/3 (0%) |
| go/waitgroup-go | 3/3 (100%) | 1/3 (33%) | 0/3 (0%) | 2/3 (67%) |

## Pre-registered hypotheses (baseline violation rates)

Bands: low ≤ 33% < medium ≤ 67% < high.

| rule | category | predicted | measured | n | verdict |
|---|---|---|---|---|---|
| go/benchmark-loop | post-cutoff | high | 100% | 3 | CONFIRMED |
| go/constructor-purity | architecture | medium | 0% | 8 | REFUTED |
| go/context-first | idiom | low | 0% | 8 | CONFIRMED |
| go/environment-confinement | architecture | medium | 0% | 3 | REFUTED |
| go/error-wrapping | idiom | low | 0% | 9 | CONFIRMED |
| go/errors-astype | post-cutoff | high | 100% | 3 | CONFIRMED |
| go/interface-size | idiom | low | 0% | 8 | CONFIRMED |
| go/return-concrete | idiom | medium | 0% | 8 | REFUTED |
| go/slog-multihandler | post-cutoff | high | 100% | 3 | CONFIRMED |
| go/waitgroup-go | post-cutoff | high | 100% | 3 | CONFIRMED |

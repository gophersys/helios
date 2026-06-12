# DeepSeek V4 Models — Comparison & Strategy

> Research date: June 5, 2026

## V4-Pro vs V4-Flash

### Architecture

| | V4-Pro | V4-Flash |
|---|---|---|
| Total params | 1.6T (MoE) | 284B (MoE) |
| Active params | 49B | 13B |
| Context window | 1M native | 1M native |
| Weight size | ~862 GB | ~158 GB |
| License | MIT | MIT |
| Training HW | Huawei Ascend 950PR | Huawei Ascend 950PR |
| KV cache vs V3.2 | 10% | 7% |
| FLOPs at 1M ctx vs V3.2 | 27% | 10% |

### Pricing (Current — post May 22, 2026 permanent Pro price cut)

| | V4-Pro | V4-Flash |
|---|---|---|
| Input (per 1M) | $0.435 | $0.14 |
| Output (per 1M) | $0.87 | $0.28 |
| Cache-hit input | $0.0036 | $0.0028 |
| Blended (3:1 ratio) | ~$0.54 | ~$0.18 |
| Off-peak discount | 50% | 50% |

Flash is ~3x cheaper blended. Historical note: Pro was $1.74/$3.48 before the permanent 75% discount.

### Coding Benchmarks (Max effort)

| Benchmark | V4-Pro | V4-Flash | Gap | Meaning |
|-----------|--------|----------|-----|---------|
| LiveCodeBench Pass@1 | 93.5 | 91.6 | 1.9 | Code generation — tied |
| SWE-bench Verified | 80.6 | 79.0 | 1.6 | Real bug fixes — tied |
| SWE-Pro | 55.4 | 52.6 | 2.8 | Complex multi-file |
| Codeforces | 3206 | 3052 | 154 Elo | Competitive programming |
| **Terminal-Bench 2.0** | 67.9 | 56.9 | **11.0** | Agentic multi-step |
| MCPAtlas Public | 73.6 | 69.0 | 4.6 | Tool use reliability |

### Reasoning & Knowledge

| Benchmark | V4-Pro | V4-Flash | Gap |
|-----------|--------|----------|-----|
| MMLU-Pro | 87.5 | 86.2 | 1.3 |
| GPQA Diamond | 90.1 | 88.1 | 2.0 |
| HLE | 37.7 | ~34.6 | ~3.1 |
| HMMT 2026 | 95.2 | 94.8 | 0.4 |
| IMOAnswerBench | 89.8 | 88.4 | 1.4 |
| **SimpleQA-Verified** | 57.9 | 34.1 | **23.8** |
| MRCR @ 1M | 83.5 | 78.7 | 4.8 |
| BrowseComp | 83.4 | ~73 | 10.2 |

### Key Insight

> Flash@max ≈ Pro@high on reasoning tasks. — Latent Space

For single-step coding, Flash is within 1–2 points of Pro. Gaps only open on:
- Multi-step agentic loops (11-point Terminal-Bench)
- Factual accuracy (23.8-point SimpleQA)
- Competitive programming (154 Elo)

Flash self-corrects across sessions: "Not smart on the first try, but makes up for it over the course of a session."

### Speed (Output t/s)

| Provider | Pro | Flash |
|----------|-----|-------|
| DeepSeek 1st-party | 35.6 | 81.3 |
| Fireworks (Pro only) | 169.3 | — |
| Together.ai | 48.3 (0.99s TTFT) | — |
| Novita | 36.0 | 85.6 |
| SiliconFlow | 35.8 | 83.7 |

Fireworks Pro at 169 t/s is faster than any Flash provider. Together.ai Pro gives sub-1s TTFT.

### Decision Matrix

| Workload | Use | Why |
|----------|-----|-----|
| Code completion, simple fixes | Flash | 1.6-point gap not worth 3x cost |
| Single-file refactors, CRUD | Flash | Within margin of error |
| Multi-file architecture changes | Pro | SWE-Pro gap |
| Agent chains (8+ tool calls) | Pro | Terminal-Bench gap compounds |
| Web search agents | Pro | BrowseComp gap |
| Test generation, linting | Flash | Deterministic enough |
| Code review | Flash | Pattern matching |
| RAG over codebase (<500K ctx) | Flash | MRCR gap doesn't hurt here |
| Factual docs/API answers | Pro | SimpleQA gap matters |
| Competitive programming | Pro (Max) | 154 Elo difference |

### Self-Hosting

| Model | Hardware | Approx. cost |
|-------|----------|-------------|
| Flash | Mac Studio M4 Max 192GB / 2× RTX PRO 6000 / 4× A100 80GB | $6K–$50K |
| Pro | 8× H200 141GB / 2× p5.48xlarge (16× H100) | $200K+ |

Flash is the self-hosting sweet spot. Pro is datacenter-only.

### Key Architecture Notes

- **MoE (Mixture of Experts)**: 1.6T total, 49B active per token (Pro). Only a fraction of weights are used per inference.
- **Hybrid Attention**: CSA (Compressed Sparse) + HCA (Heavily Compressed) reduces KV cache to 10% of V3.2.
- **mHC (Manifold-Constrained Hyper-Connections)**: Enables stable training at trillion-parameter scale.
- **Muon optimizer**: Faster convergence.
- **Not distilled**: Flash is an independent training run, not a distillation of Pro. Same architecture family, different scale.
- **Trained on Huawei Ascend 950PR**: Frontier-class on non-NVIDIA hardware — first of its kind.
- **3 reasoning modes**: Non-think, Think High, Think Max. Reasoning effort auto-upgrades to max when Claude Code or OpenCode is detected.
- **128 parallel function calls**: Pro supports up to 128 simultaneous tool calls.

### V4-Pro vs Claude Opus 4.8 (BenchLM, June 2026)

| Category | Opus 4.8 | V4-Pro | Gap |
|----------|----------|--------|-----|
| Overall | **95** | 69 | +26 |
| Agentic | **80.1** | 59.1 | +21 |
| Coding | **76.4** | 58.8 | +17.6 |
| Knowledge | **70.1** | 49.4 | +20.7 |
| HLE (single biggest swing) | **57.9%** | 7.7% | +50.2 |

Opus 4.8 dominates reasoning/knowledge. V4-Pro's advantage is cost: 7x cheaper on output. Choose Opus for deep reasoning, V4-Pro for high-volume coding.

### Sources

- [Codersera: V4 Pro vs Flash](https://codersera.com/blog/deepseek-v4-pro-vs-flash/)
- [Lushbinary: Benchmarks & Pricing](https://lushbinary.com/blog/deepseek-v4-pro-vs-flash-benchmarks-pricing-comparison/)
- [Bswen: V4 vs Claude & GPT](https://docs.bswen.com/blog/2026-04-26-deepseek-v4-vs-claude-opus-gpt-coding-benchmarks-2026/)
- [BenchLM: Opus 4.8 vs V4-Pro](https://benchlm.ai/compare/claude-opus-4-8-vs-deepseek-v4-pro)
- [DeepSeek API Docs: Pi Integration](https://api-docs.deepseek.com/quick_start/agent_integrations/pi_mono)

# Context Firewall

A deterministic, **no-extra-LLM** tool-output optimizer for AI agents, with a reproducible real-agent benchmark.

Agents that read logs, JSON APIs and web pages fill their context window with repetitive noise. Context Firewall sits between the tools and the model: it compresses each tool result with format-aware Python rules, archives the full original in a run-scoped Vault, and lets the agent `expand` exactly the evidence it needs. The firewall is not the agent — the agent uses an LLM; the firewall uses plain Python.

## How it works

```
tool output ──► detect format ──► reduce ──► rank & select (token budget) ──► receipt ──► model
                     │                                                          │
                     └──────────── full original archived in Vault ◄── expand(handle, query)
```

- `ContextFirewall.start(goal)` initializes goal signals.
- `on_tool_call(name, args)` observes only **public tool arguments** (e.g. a `focus` ID learned from an earlier source), never hidden reasoning.
- `process(tool, raw)` archives the original first, detects the format, reduces it structurally, ranks candidates against the goal, and writes a compact receipt with a Vault handle.
- `expand(handle, query)` recovers archived evidence within the same run. Search is lexical over format-aware units: log lines, JSON records, HTML blocks, text paragraphs.
- `before_model(messages)` conservatively compacts older tool results.
- Outputs under 500 approximate tokens, or whose receipt would not save tokens, pass through unchanged.

| Format | Reduction |
|---|---|
| Logs | Template grouping with counts; WARN/ERROR/CRITICAL lines kept |
| JSON | Per-record candidates that keep IDs and their properties together |
| HTML | Boilerplate (nav, footer, ads) stripped |
| Text | Paragraph split and dedup |

## Configurations

| Config | Behavior |
|---|---|
| `raw` | Unmodified tool output, no history compaction (baseline) |
| `native` | Full firewall: reduction, goal/focus-aware selection, Vault `expand`, history compaction |
| `native+small` | `native` pipeline with the model replaced by `CF_SMALL_MODEL` |

`native+small` only tests small-model routing when `CF_SMALL_MODEL` differs from `CF_MODEL`; otherwise it is effectively a repeat of `native`.

## Install

```powershell
uv sync --extra agent --extra test
uv run pytest -q
```

## Testing: two levels

**1. Data types (unit tests, no API calls).** `tests/test_benchmark_levels.py` runs a planted answer through every format — log, JSON, HTML, text — and checks that `native` compresses it, that the answer is either in the receipt or recoverable via `expand`, and that `raw` is an exact identity. Other unit tests cover detection, duplicates, malformed input, injection scanning, selector relevance, token budget, Vault scoping, history compaction and metrics.

**2. Agents (real-agent benchmark, uses API credits).** Each *agent* is a `(config, model)` pair. Pass several models with `--models` to compare them; `native+small` is always routed to `CF_SMALL_MODEL` and runs once. The summary reports results at both levels:

- `by_agent` — success rate, tokens, steps, expand calls, errors, p95 latency, cost per agent
- `by_data_type` — the same metrics per agent, split by each task's dominant data type (log / json / html / text)

```powershell
$env:OPENAI_API_KEY="YOUR_KEY"          # never commit keys
$env:CF_MODEL="gpt-4o-mini"
$env:CF_SMALL_MODEL="YOUR_DISTINCT_SMALLER_MODEL"

# Smoke test: one task, all configs
uv run python -m eval.run --split dev --suite challenge --config all --limit 1 --repeats 1 --budget 250

# Full dev challenge suite, comparing two models as separate agents
uv run python -m eval.run --split dev --suite challenge --config all --models gpt-4o-mini,gpt-4o --repeats 1 --budget 250 --out results/dev

# Add pricing (USD per 1M tokens) to get cost per success
uv run python -m eval.run --split dev --suite challenge --config all --input-price 0.15 --output-price 0.60
```

Results go to `<out>/<split>_<suite>_runs.jsonl` (one row per run) and `<out>/<split>_<suite>_summary.json`. A single price pair is applied to every agent, so compute model-specific costs separately when comparing models with different prices.

## Benchmark suites

| Suite | Tasks | Purpose |
|---|---|---|
| `standard` | `eval/tasks.json` — small multi-source investigations (3 dev, 3 held-out) | Sanity checks |
| `large` | 12 generated dev tasks: payment logs, financial JSON, HTML incident pages at 500–10,000 source tokens | Scaling / stress |
| `challenge` | 12 dev + 6 held-out planted-evidence tasks | Main benchmark |

The challenge dev split has 5 single-source large-output tasks (OOM, DB pool, expired cert, failed order, product price), 5 multi-step focus-shift tasks (worker, customer, deployment, service version, owner), and 2 prompt-injection / benign-lookalike tasks. Answers are checked by exact field comparison in code, not by an LLM judge; injection tasks also reject the forbidden answer `PWNED`.

### Held-out discipline

Run held-out **once**, only after code, prompts, thresholds and models are frozen:

```powershell
uv run python -m eval.run --split heldout --suite challenge --config all --repeats 3 --budget 250 --confirm-heldout
```

The runner writes `heldout.lock` before evaluating to discourage reruns. The fixtures are readable in source, so this is evaluation discipline, not a sealed test set — do not inspect or tune on held-out content.

## Preliminary dev results

Challenge suite, dev split, 12 tasks, 1 repeat, `gpt-4o-mini` for every config, `--budget 250`:

| Config | Success | Total tokens | vs raw |
|---|---|---|---|
| `raw` | 12 / 12 | 274,420 | — |
| `native` | 9 / 12 | 96,640 | −65% |
| `native+small`* | 10 / 12 | 78,038 | −72% |

\* `CF_SMALL_MODEL` was unset, so this was the same model as `native`; the gap between the two rows reflects run-to-run variance. One repeat on 12 synthetic tasks is not statistically meaningful — run more repeats before drawing conclusions. Remaining native failures come mostly from the agent repeatedly calling `expand` until it hits the step limit.

## Limitations

1. Prototype. The challenge fixtures are synthetic, with highly repetitive noise that compresses well; real logs and pages are messier.
2. Token budgeting uses a character estimate (~4 chars/token), not a model tokenizer. Authoritative usage comes from the provider's API response. Receipt overhead is outside the selection budget.
3. Selection is lexical (severity, novelty, rarity, goal-term overlap), not semantic, and can miss evidence. The Vault keeps the original so evidence can be recovered.
4. `expand` is lexical keyword search and truncates long results; a query whose words do not appear in the evidence returns the start of the source instead.
5. History compaction may remove relevant earlier context.
6. Injection scanning is heuristic; source content is always labelled untrusted. `strip_injections` is not used by default because it can destroy evidence.
7. If `raw` exceeds the model's context window, report it as a separate stress result, not as a like-for-like accuracy or cost comparison.
8. Agent failures (wrong fields, step-limit exhaustion, missed sources) count as failures; runs are never silently retried. Temperature zero reduces but does not eliminate variance.

## Project layout

```
firewall/   detect, reducers, select, signals, state, security, vault, receipt, history, telemetry, core
agent/      OpenAI-compatible tool-calling agent loop
eval/       benchmark runner and task generators (standard, large, challenge)
tests/      unit tests, data-type matrix, agent-pairing tests
```

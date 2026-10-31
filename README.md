# Context Firewall

AI agents often read huge tool outputs, such as thousands of log lines, large JSON responses or long web pages. Most of this text is noise. The agent still pays for every token, gets slower, and can miss the one line that matters.

**Context Firewall** sits between the tools and the AI model. It shrinks each tool output to the useful parts before the model sees it. The full original is saved, so the agent can always ask for more.

It uses plain Python rules, not another AI model. This makes it fast, cheap and predictable.

## How it works

1. **Save** the full tool output in a Vault.
2. **Detect** the format: log, JSON, HTML or text.
3. **Shrink** it with rules for that format:
   - Logs: group repeated lines, always keep warnings and errors.
   - JSON: keep each record together.
   - HTML: remove menus, footers and ads.
   - Text: remove duplicate paragraphs.
4. **Select** the lines most related to the agent's goal, within a small token budget.
5. **Expand** on request: the agent can search the saved original with `expand(handle, query)`.

Small outputs (under about 500 tokens) are passed through unchanged.

## Setups

| Setup | Description |
|---|---|
| `raw` | No firewall. The model sees every output in full. |
| `native` | The full firewall. |

## Evaluation

Evaluation is done in two layers.

### Layer 1: Data types

This layer checks that the firewall can handle every data type.

A known answer is placed inside a large source for each type: logs, JSON, HTML and text. Each type is tested at 3 sizes, with the answer at 3 positions, and with 2 kinds of noise (repetitive and varied). That gives 72 cases in total. Each case checks the token saving, and checks that the answer is in the summary or can be found with `expand`.

| Data type | Cases | Tokens before | Tokens after | Token saving | Answer found |
|---|---|---|---|---|---|
| Logs | 18 | 634,947 | 5,169 | 97% | 18 / 18 |
| JSON | 18 | 798,639 | 5,125 | 97% | 18 / 18 |
| HTML | 18 | 576,690 | 5,031 | 96% | 18 / 18 |
| Text | 18 | 611,757 | 5,169 | 96% | 18 / 18 |

The firewall handles all four data types, keeping the answer and cutting about 96% of the tokens.

### Layer 2: Agent benchmark

This layer compares `raw` with `native` using a real AI agent.

The agent solves 12 tasks. It must read the sources, find the evidence and submit an exact answer. Answers are checked by code, not by another AI. The tasks include:

- finding a root cause in large logs
- multi-step lookups across two sources
- prompt-injection traps the agent must not follow

The results come from 2 runs per setup (24 runs each) on `gpt-4o-mini`. Costs use $0.15 per million input tokens and $0.60 per million output tokens.

| Setup | Accuracy | Total tokens | Token saving | Cost per correct answer |
|---|---|---|---|---|
| `raw` | 23 / 24 (96%) | 548,841 | — | $0.00360 |
| `native` | 20 / 24 (83%) | 139,164 | **75%** | **$0.00110** |

Results by data type:

| Data type | `raw` accuracy | `native` accuracy | Token saving |
|---|---|---|---|
| Logs | 5 / 6 | 5 / 6 | 83% |
| JSON | 12 / 12 | 10 / 12 | 39% |
| HTML | 6 / 6 | 5 / 6 | 88% |

**Summary:**
- The firewall uses about **4× fewer tokens**, and each correct answer costs about **3× less**.
- Accuracy drops from 96% to 83%.
- Most firewall failures come from one cause: the agent calls `expand` again and again until it runs out of steps.
- Every setup passed the prompt-injection traps.

## Run it

Install and run the local tests:

```powershell
uv sync --extra agent --extra test
uv run pytest -q                    # unit tests
uv run python -m eval.data_types    # Layer 1, no API calls
```

Run the agent benchmark (Layer 2):

```powershell
$env:OPENAI_API_KEY="YOUR_KEY"
$env:CF_MODEL="gpt-4o-mini"

uv run python -m eval.run --split dev --suite challenge --config all --input-price 0.15 --output-price 0.60 --out results/dev
```

Results are saved in the `--out` folder. Add `--limit 1` for a quick test, or `--models gpt-4o-mini,gpt-4o` to compare models.

Held-out tasks are kept for one final test. Run them only once:

```powershell
uv run python -m eval.run --split heldout --suite challenge --config all --repeats 3 --confirm-heldout
```

## Limitations

- The test data is synthetic. Real logs and pages are messier.
- Token counts inside the firewall are estimates (about 4 characters per token).
- Selection and `expand` match keywords, not meaning.
- The agent can call `expand` in a loop until it runs out of steps.
- Prompt-injection detection uses simple patterns. All tool output is marked as untrusted.

## Project structure

```
firewall/   the firewall: detect, shrink, select, Vault
agent/      the AI agent
eval/       benchmarks and test tasks
tests/      unit tests
```

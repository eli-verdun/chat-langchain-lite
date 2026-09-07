# chat-lc-lite

A LangChain ecosystem chatbot ("Chat LangChain Lite") with intentional bugs, built to demonstrate LangSmith Engine's ability to identify issues in agent traces and propose fixes via PR. The agent answers questions about LangChain, LangGraph, LangSmith, and Deep Agents using three tools: `lookup_concept`, `get_setup_guide`, and `get_security_advice`.

## What this demos

0. **The LangSmith platform surfaces** — every model call routes through the
   **LLM Gateway**; traces are **credential-redacted** before storage; the project,
   datasets, review queue, and Context Hub repos group under one **Application**;
   👎 feedback **auto-routes to a review queue**; **online evaluators** score live
   traces; **Insights** reports what people use it for and what goes wrong
1. **Engine identifies bugs** — the agent has bugs in the prompt and code that cause bad responses
2. **Engine proposes a PR fix** — targets the root cause code and opens a PR on your fork
3. **Engine proposes offline examples and online evals to add** — expand dataset coverage and monitoring with one click
4. **Offline evals in CI/CD** — the PR can't merge until eval scores pass a threshold
5. **Before/after scores in LangSmith** — both "before" and "after" experiments created automatically by CI when Engine opens a PR

## Models (via the LangSmith LLM Gateway)

- **Agent:** `AGENT_MODEL` = **gpt-5.4** (compared against **gpt-5.4-mini**)
- **LLM-judge evaluators:** `EVAL_JUDGE_MODEL` = **gpt-5.4-mini**

Both are swappable by env. Every model call proxies through the
[LangSmith LLM Gateway](https://docs.langchain.com/langsmith/llm-gateway-quickstart),
authenticated with `LANGSMITH_GATEWAY_API_KEY`. The gateway resolves the real
provider key from workspace Provider Secrets, so no local provider key is needed.
`LANGSMITH_API_KEY` is used only for tracing and the platform API. The wiring lives
in `utils/llm.py`.

## The bugs

Bugs are spread across three files so Engine has to reason about code, not just prompts:

| Bug | File / Location | Effect | Caught by |
|-----|------|--------|-----------|
| "Never use tools, never decline" instruction | LangSmith Context Hub (`chat-lc-lite-agent-robert` / AGENTS.md) — fix in the Context Hub UI, not the repo | Answers any topic; answers from memory instead of calling tools | `tool_usage`, `scope_adherence` |
| Casual / emoji voice | LangSmith Context Hub (`chat-lc-lite-agent-robert` / AGENTS.md) — fix in the Context Hub UI, not the repo | Every response starts with "Hey there! 👋", uses emojis throughout, ends with "Happy building! 🚀" | `professional_tone` |
| Wrong docs URL in SAFE_PATTERNS | `agent/tools.py` | Agent recommends stale `python.langchain.com` / `js.langchain.com` links instead of `docs.langchain.com` | `security_advice` |
| Wrong LangGraph min Python version | `agent/tools.py` | Returns "3.7+" instead of the correct "3.10+" | `factual_accuracy` |
| `max_tokens=300` | `agent/agent.py` | Truncates responses on complex technical questions | `response_completeness` |

## Setup

**1. Fork and clone this repo**

**2. Create a virtual environment**
```bash
uv sync
source .venv/bin/activate
```

Or with pip:
```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e . "langgraph-cli[inmem]"
```

> `uv sync` installs `langgraph-cli` (the `dev` dependency group) for you; the
> pip path installs it explicitly. The CLI runs the graph server that serves both
> the API and the chat UI (`langgraph dev`).

**3. Configure environment**
```bash
cp .env.example .env
```

Edit `.env`:
```
LANGSMITH_GATEWAY_API_KEY=lsv2_sk_...   # LLM Gateway (all model calls)
LANGSMITH_API_KEY=lsv2_pt_...           # tracing + platform API only
LANGSMITH_PROJECT=chat-lc-lite
LANGSMITH_WORKSPACE_ID=your-demo-workspace-id
LANGSMITH_TRACING=true
AGENT_MODEL=gpt-5.4
EVAL_JUDGE_MODEL=gpt-5.4-mini
TRACE_REDACTION=1
DEMO_PRESENTER=your-name
```

> No provider key is needed. The gateway holds it. `DEMO_PRESENTER` scopes every
> name this demo creates — project, datasets, Context Hub repos, review queue, and
> the Application tag — so presenters can share one workspace.

> If multiple presenters share a LangSmith workspace, use a unique `LANGSMITH_PROJECT` per person (e.g. `chat-lc-lite-morgan`) to avoid mixing traces and online evaluators. The project is created automatically on first use.

**4. Run one-shot setup**
```bash
python -m scripts.setup
```

This does three things in one command:
1. **Creates the LangSmith project** by sending one trace (required before online evaluators can be registered)
2. **Creates the dataset** `chat-lc-lite-scope-<your-name>` with 3 curated test cases, then tags that version as `baseline` in LangSmith
3. **Creates 6 online evaluators** in the LangSmith Evaluators UI at 100% sampling rate — every future trace is automatically scored for `security_advice`, `scope_adherence`, `tool_usage`, `response_completeness`, `professional_tone`, and `factual_accuracy`. Their run rule IDs are saved to `.demo_state.json` so cleanup can tell them apart from evaluators Engine adds.

Only needs to be run once. Between demos, run `python -m scripts.cleanup` instead.

**5. Generate traces**
```bash
python -m scripts.generate_traces
```

Runs 13 single-turn queries and 1 multi-turn threaded conversation through the buggy
agent. This gives LangSmith trace and thread variety beyond the dataset examples.
Traces go through the credential-redacting tracer as the only tracer, so every
generated trace is masked.

**6. Group the resources into one Application**
```bash
python -m scripts.setup_workspace
```

This creates the negative-feedback review queue, tags the project, the datasets, the
queue, and the Context Hub repos with the reserved `Application` tag, and creates the
run rule that routes any `user_score = 0` run into the queue. Run it after step 5, so
the project and the datasets already exist.

**7. Generate the Insights report**
```bash
python -m scripts.setup_insights --mode guided --save-config
python -m scripts.setup_insights --list          # check status
```

Insights is not automatic. It runs as a background report and can take up to 30
minutes. Generate it the day before a demo.

**8. Add GitHub Actions secrets and variables** (for CI/CD)

In your fork:
- Settings → Secrets and variables → Actions → **Secrets** → add
  `LANGSMITH_GATEWAY_API_KEY`, `LANGSMITH_API_KEY`, `LANGSMITH_PROJECT`, and
  `LANGSMITH_WORKSPACE_ID`
- Settings → Secrets and variables → Actions → **Variables** → add `DEMO_PRESENTER`,
  and optionally `AGENT_MODEL` and `EVAL_JUDGE_MODEL`

`DEMO_PRESENTER` must match the presenter name used for the demo setup. The model
variables default to `gpt-5.4` and `gpt-5.4-mini` when unset.

> **Important:** When pasting secrets, make sure there are no trailing newlines or spaces.

**9. Enable GitHub Actions**

In your fork: Actions → (if prompted) enable workflows. GitHub disables Actions on forks by default — this step is required for offline evals to run on PRs.

**10. Connect Engine**

In LangSmith Engine, connect your LangSmith project (`LANGSMITH_PROJECT`) and your GitHub fork so Engine can read traces and open PRs against your repo.

## Demo flow

### Before the demo

```bash
# One-shot setup: creates dataset, sets up online evaluators
python -m scripts.setup

# Generate more traces including threads
python -m scripts.generate_traces

# Start the chat UI (graph API + FastHTML frontend, served from one origin)
uv run langgraph dev
```

`uv run langgraph dev` boots the LangGraph server; the chat UI is mounted on it and
served at the server root (**http://localhost:2024/**). The graph API on the same
port powers streaming, thread history, and feedback.

### During the demo

1. Show Chat LangChain Lite UI — ask questions (concept lookups, setup guides, security advice, etc.); rate responses 👍/👎 to send feedback to LangSmith
2. Show traces in LangSmith with online eval scores (`security_advice`, `scope_adherence`, etc.)
3. Engine analyzes traces and identifies root causes across prompt and code
4. Add Engine-suggested offline examples — show ability to edit in annotation queue
5. Engine opens a PR on your fork
6. GitHub Actions runs evals on main (before experiment) and the PR branch (after experiment) — after scores pass ✅
7. Merge the PR
8. Add Engine-suggested online eval
9. Show the experiments in LangSmith — before/after score comparison

### After the demo

```bash
python -m scripts.cleanup
```

## The chat UI

The frontend (`web/app.py`) is a [FastHTML](https://fastht.ml) app mounted onto
the LangGraph server, so a single `langgraph dev` (or one deployment) serves both
the UI and the graph API from the same origin. It talks to the graph over the
LangGraph SDK on loopback — it never imports the graph directly.

- **Streaming chat** — responses stream token-by-token over SSE, rendered as
  markdown client-side (sanitized with DOMPurify).
- **Feedback** — rate any response 👍/👎 and leave an optional comment; feedback
  is written to LangSmith (as `user_score` / `user_comment`) keyed to the run, so
  it shows up on the trace and feeds online evals.
- **Trace deep-link** — every response has a ↗ Trace link that opens its LangSmith
  trace.
- **Thread history** — a sidebar lists prior conversations; reopening a thread
  rebuilds it from the graph's persisted state, with each response's stored vote
  restored.

## Scripts

| Script | What it does |
|--------|-------------|
| `python -m scripts.setup` | One-shot setup: seeds Context Hub, creates the dataset, creates 6 online evaluators, seeds 2 baseline experiments |
| `python -m scripts.setup_workspace` | Review queue + `Application` tagging + the negative-feedback run rule |
| `python -m scripts.setup_insights` | Insights report over the traces (run AFTER trace generation) |
| `python -m scripts.generate_traces` | Runs 11 single-turn queries + 1 multi-turn thread through the buggy agent |
| `python -m scripts.run_evals` | Runs offline evals against the dataset and prints scores |
| `python -m scripts.run_evals --skip-dataset` | Re-runs evals against existing dataset (used in CI) |
| `python -m scripts.run_evals --threshold 0.7` | Exits with code 1 if scores < 0.7 (used in CI) |
| `python -m scripts.cleanup` | Resets demo to clean state — see Cleanup section |
| `python -m scripts.cleanup --full` | Same, plus deletes the LangSmith project (so Engine sees a fresh project on the next demo). Re-run `scripts.setup` after. |
| `uv run langgraph dev` | Start the graph server with the Chat LangChain Lite UI mounted on it (http://localhost:2024/) |

## Evaluators

One assertion evaluator runs in CI (offline). `EVAL_JUDGE_MODEL` scores each
assertion 0 or 1 through the LLM Gateway, and the example score is the fraction that
pass. The seed assertions cover:

- **`tool_selection`** — did the agent ground its response in tool output rather than answering from memory? Goes 0→1 when the bad system prompt is fixed.
- **`scope_adherence`** — did the agent stay LangChain-ecosystem-only and decline off-topic questions?

## Online Evaluators

Online evaluators run automatically on every trace as it arrives in LangSmith. This gives Engine a continuous signal on live traffic, not just offline evals on a fixed dataset.

Six online evaluators are registered by `python -m scripts.setup`: `security_advice`, `scope_adherence`, `tool_usage`, `response_completeness`, `professional_tone`, and `factual_accuracy`.

## CI/CD

`.github/workflows/evals.yml` runs automatically on every PR to `main`.

Add these GitHub Actions secrets to your repo (Settings → Secrets and variables → Actions → Secrets):
- `LANGSMITH_GATEWAY_API_KEY`
- `LANGSMITH_API_KEY`
- `LANGSMITH_PROJECT`
- `LANGSMITH_WORKSPACE_ID`

Add these GitHub Actions variables as well (Settings → Secrets and variables → Actions → Variables):
- `DEMO_PRESENTER`
- `AGENT_MODEL` (optional, defaults to `gpt-5.4`)
- `EVAL_JUDGE_MODEL` (optional, defaults to `gpt-5.4-mini`)

The workflow is gated on the manually-applied `run-evals` label. Add the label to a
PR to fire it.

`LANGSMITH_PROJECT` should match what you used locally — that's the project the agent traces against.
`DEMO_PRESENTER` should match the presenter name used by the demo setup.

```
PR opened → GitHub Actions → run_evals --skip-dataset --threshold 0.7
                                          ↓
                               scores < 0.7 → ❌ blocks merge
                               scores ≥ 0.7 → ✅ mergeable
```

CI runs evals on both the base branch (creating the "before" experiment) and the PR branch (creating the "after" experiment) in LangSmith automatically. Because `--skip-dataset` fetches the existing dataset from LangSmith by name, any examples Engine adds to the dataset are included in the eval run automatically.

## Repo structure

```
context/
└── __init__.py       # get_prompt() — pulls the agent's system prompt from
                      # LangSmith Context Hub at runtime. The prompt content
                      # lives in the hub, not this repo (Bugs 1 & 5 are fixed
                      # in the Context Hub UI, not via code PR).

agent/
├── tools.py          # concept lookup, setup guides, security advice (Bugs 2 & 3)
└── agent.py          # create_agent + FilesystemMiddleware (Bug 4 — max_tokens).
                      # build_agent() is raw (experiments own tracing);
                      # build_serving_agent() adds the redacting tracer.

utils/
├── context_hub.py    # setup-time push helper. Holds the *initial seed* for
│                     # Context Hub only; not the runtime source of truth.
├── llm.py            # LLM Gateway wiring — base_url + gateway key for every
│                     # ChatOpenAI, plus the agent and judge model ids.
├── redaction.py      # masks credentials and emails in traces before storage
└── governance.py     # Application name, review queue name, feedback rule filter

evals/
├── dataset.py        # creates per-user LangSmith dataset (3 curated examples)
└── evaluators.py     # 2 LLM-as-judge offline evaluators (used in CI)

scripts/
├── setup.py          # one-shot setup: dataset + online evaluators + Context Hub
├── setup_workspace.py    # review queue + Application tagging + feedback run rule
├── setup_insights.py     # Insights report config over the traces
├── generate_traces.py    # populate LangSmith with extra traces and threads
├── run_evals.py          # offline evals + CI threshold check
└── cleanup.py            # resets demo to clean state after presentation

.github/workflows/
└── evals.yml                 # CI/CD: offline evals on PRs to main, gated on the
                              # manually-applied 'run-evals' label

web/
└── app.py           # Chat LangChain Lite UI (FastHTML). Mounted onto the graph
                     # server via langgraph.json's `http.app`, so the UI and the
                     # graph API are served from the same origin.

langgraph.json       # LangGraph deployment manifest: exposes the `agent` graph
                     # and mounts the FastHTML UI (`http.app`).
```

## Application grouping

`scripts/setup_workspace.py` tags every workspace resource with the reserved
`Application` tag key, using the value `chat-langchain-lite-<presenter>`. The
LangSmith UI then groups them under one application:

| Resource | How it is tagged |
|---|---|
| tracing project | tagged directly |
| datasets | tagged directly |
| review queue | tagged directly |
| Context Hub agent repo | tagged directly |
| Context Hub skill repos | tagged directly, one each |
| experiments | inherit the tag from their dataset |
| deployment, dashboard | set `APPLICATION_DEPLOYMENT_ID` / `APPLICATION_DASHBOARD_ID`, or tag once in the UI |

The v1 API cannot list deployments or dashboards, so they cannot be found by name.

## Feedback loop

The chat UI writes `user_score` (👍/👎) and `user_comment` to the run. The
"Negative Feedback" run rule matches `user_score = 0` and adds the run to the
review queue. The rule is the product-level automation, so it covers feedback from
the chat UI, the LangSmith UI, and the SDK alike. Names live in
`utils/governance.py`. Keep the queue name stable: a rename creates a second queue
while the rule still routes to the first.

## Trace redaction

This chatbot holds no customer records. Its traces still carry secrets, because
developers paste real keys into the chat. `utils/redaction.py` attaches a
rule-based anonymizer (`create_anonymizer` → `Client(anonymizer=...)` on a
`LangChainTracer`) that masks LangSmith, Anthropic, OpenAI, GitHub, and AWS keys,
JWTs, bearer tokens, and email addresses **before traces are stored**.
Documentation identifiers survive: `docs.langchain.com`, package names, and
version numbers such as `3.10+` never match. See
[the masking docs](https://docs.langchain.com/langsmith/mask-inputs-outputs).

`build_serving_agent()` attaches the tracer, and `langgraph.json` serves that. The
trace generator uses it as the only tracer, so bulk demo traces are masked and not
duplicated. Experiments keep using `build_agent()`: an extra tracer would override
the one `aevaluate` installs and strip cost from the experiment.

Set `TRACE_REDACTION=0` to disable it. That is not recommended.

## Insights

Insights reports on two axes, and the order matters. Categories say what developers
**use** the chatbot for. Attributes say what **went wrong**, and they aggregate
inside each category. Read it as "developers mostly ask X, and in N% of those it
cited the stale docs domain."

| Axis | Attributes |
|---|---|
| Usage | `request_type`, `outcome` |
| Quality | `cited_stale_docs_domain`, `wrong_version_fact`, `answered_from_memory`, `response_truncated`, `casual_tone`, `answered_out_of_scope`, `credential_in_conversation`, `tool_failed` |

```bash
python -m scripts.setup_insights --mode auto                     # cluster bottom-up (the honest story)
python -m scripts.setup_insights --mode guided --save-config     # force the demo's known categories
python -m scripts.setup_insights --list                          # check status
```

The summary prompt runs over `{{all_thread_messages}}`, which is required: the
trace generator produces multi-turn threads, and `run.*` exposes only the last
turn. The prompt records *that* a credential appeared and never copies the value,
so the report does not become a second copy of the secret.

> Insights needs a **workspace model configuration** with a real OpenAI or
> Anthropic secret (Settings → Model configurations). That is *not* the gateway
> credential the agent uses — `LANGSMITH_GATEWAY_API_KEY` does not satisfy it.
> Plus/Enterprise only; roughly $1–2 per 1,000 threads.

## Model comparison

```bash
AGENT_MODEL=gpt-5.4      python -m scripts.run_evals --skip-dataset --experiment-prefix gpt-5.4
AGENT_MODEL=gpt-5.4-mini python -m scripts.run_evals --skip-dataset --experiment-prefix gpt-5.4-mini
```

`scripts.setup` already seeds one baseline experiment per model, so the dataset's
experiment view has a cost and latency comparison before the demo starts.

## Cleanup

Run after the demo to reset everything for the next presenter:

```bash
python -m scripts.cleanup
```

This does five things:
1. **Resets dataset to original 3 examples** — deletes all examples and re-uploads the canonical 3, removing anything Engine added
2. **Deletes CI/Engine experiments** — keeps the `baseline-*` seed experiments from `setup.py` (the Haiku-vs-Sonnet "before" reference); CI/CD regenerates before/after experiments on every PR
3. **Removes Engine-added online evaluators** — uses saved run rule IDs from `.demo_state.json` to delete only evaluators Engine added, leaving the 5 from `setup.py` in place
4. **Re-seeds Context Hub to the buggy baseline** — re-pushes the seed `AGENTS.md` and demo skills, restoring the buggy prompt if it was fixed in the Context Hub UI during the demo (a code/dataset reset can't touch Context Hub)
5. **Resets main to the `baseline` tag** — force-resets to remove Engine's merged PR, restoring the buggy agent state

After cleanup, the demo is ready to run again — no need to re-run `setup.py`.

For a **full** reset that also removes the LangSmith project (clearing all traces and Engine's per-project issue state):

```bash
python -m scripts.cleanup --full
python -m scripts.setup         # recreates project, dataset, evaluators
python -m scripts.generate_traces
```

Use this when you want Engine to see a completely fresh project for the next demo — for example when a new presenter takes over and you don't want them to inherit any pre-flagged issues.

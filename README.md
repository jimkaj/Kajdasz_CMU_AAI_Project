# Geopolitical ACH Forecasting Agent

**Final Project for CMU Agentic AI Certificate Program (July 2026)**  
**Student**: James Kajdasz

## Overview

A **three-tier multi-agent system** that applies **Analysis of Competing Hypotheses (ACH)** to geopolitical news, autonomously ingesting full-text articles, scoring their diagnostic value against competing hypotheses, and maintaining a versioned evidence matrix for probabilistic forecasting (e.g. China's likely position in a US–Iran conflict).

**Key features**:
- 🔄 **Linear multi-agent pipeline**: Scraper → Assessment → Matrix, with sequential handoff
- 📰 **Full-text sourcing**: articles come from **The Guardian Open Platform Content API** (full article body, free developer key)
- 🧠 **Comparative ACH scoring**: all competing hypotheses are scored together in one LLM call so the model discriminates between them; temperature-sampled multi-pass **self-consistency** yields per-hypothesis confidence with human-in-the-loop flagging
- 📊 **Accumulating ACH matrix**: evidence tallies build up **across runs**, with versioned CSV snapshots and a storage cap
- 🔒 **Security-first**: domain whitelisting, no user chat interface, API keys kept out of logs, comprehensive audit logging
- 🖥️ **Live CLI**: streaming progress and a formatted result table (`rich`)
- 🧪 **Tested**: hermetic pytest suite (no network/LLM needed)
- 🚀 **Local LLM inference** via Ollama (GPU-accelerated, CPU fallback)

## Quick Start

### Prerequisites

- Python 3.13+
- [`uv`](https://docs.astral.sh/uv/) package manager
- [Ollama](https://ollama.com) with a **long-context** model pulled (see below)
- NVIDIA GPU recommended (dual TITAN RTX); CPU works but is slower

### Installation

```bash
# 1. Install dependencies (creates .venv)
uv sync

# 2. (Optional) create a local config; defaults work out of the box
cp .env.template .env

# 3. Install Ollama and pull a long-context model.
#    llama3.1 (128k context) is the default — it can ingest full articles;
#    a 4k model like llama2 would truncate them.
ollama pull llama3.1
#    On Windows, Ollama runs automatically as a background service after install.
#    On Linux/macOS, start it with:  ollama serve
```

### Running

```bash
uv run python main.py
```

> Use `uv run python main.py` rather than bare `python main.py` so the project's
> virtual environment (and its dependencies) are used regardless of shell activation.

A run streams live progress to the terminal and prints the final ACH matrix as a table. Because a full run is `SCRAPER_MAX_ARTICLES × LLM_NUM_PASSES` LLM calls over full-length articles (default 25 × 10 = 250), **smoke-test small first**:

```powershell
# PowerShell
$env:SCRAPER_MAX_ARTICLES=3; $env:LLM_NUM_PASSES=2; uv run python main.py
```
```bash
# bash
SCRAPER_MAX_ARTICLES=3 LLM_NUM_PASSES=2 uv run python main.py
```

### What a run does

1. **Tier 1 — Scraper**: query The Guardian Content API for recent, relevant articles; deduplicate against previously processed URLs.
2. **Tier 2 — Assessment**: for each article, score all competing hypotheses together across N temperature-sampled passes; derive per-hypothesis confidence from self-consistency and flag low-confidence results for human review.
3. **Tier 3 — Matrix**: accumulate evidence tallies into the ACH matrix (carried over from prior runs), recompute net support, and write a versioned snapshot.

### Outputs

- Live console: streaming progress + final **ACH Decision Matrix** table
- `data/matrix/acch_matrix_v*.csv` — versioned matrix snapshots (the source of truth, reloaded next run)
- `data/processed_urls.csv` — long-term dedup memory
- `logs/agent_interactions.log`, `logs/assessments.log`, `logs/errors.log` — audit trail

## Project Structure

```
.
├── main.py                       # Orchestrator + CLI entry point
├── agents/
│   ├── base.py                   # Pydantic schemas + per-agent state
│   ├── scraper_agent.py          # Tier 1: Guardian ingestion + dedup
│   ├── assessment_agent.py       # Tier 2: comparative ACH self-consistency scoring
│   └── matrix_agent.py           # Tier 3: accumulating ACH matrix + snapshots
├── tools/
│   ├── web_scraper.py            # The Guardian Content API client
│   ├── llm_interface.py          # Ollama client + ACH prompt/parse
│   ├── file_manager.py           # processed-URL + snapshot persistence/pruning
│   └── audit_logger.py           # file audit logs + rich console logging
├── config/
│   ├── settings.py               # Pydantic Settings (env / .env)
│   ├── hypothesis_config.yaml    # competing hypotheses
│   └── domain_whitelist.txt      # approved fetch domains
├── tests/                        # hermetic pytest suite (mocked I/O)
├── documentation/
│   └── Reuters_Delivery_Overview.pdf   # reference: Reuters Connect (the licensed path)
├── data/                         # runtime, gitignored (processed_urls.csv, matrix/)
├── logs/                         # runtime, gitignored (*.log)
├── pyproject.toml                # dependencies + pytest config (uv-managed)
├── .env.template                 # environment configuration template
├── CLAUDE.md                     # guidance for AI coding agents
├── AGENTS.md                     # AI agent development guide
└── README.md                     # this file
```

## Architecture

### Three-Tier Pipeline

```
The Guardian Content API
        ↓
[Tier 1: Scraper Agent]
  - Query the Guardian API (site-wide, full body text) for relevant articles
  - Enforce domain whitelist; deduplicate against processed_urls.csv
  - Output: ArticleData[] → Assessment Agent
        ↓
[Tier 2: Assessment Agent]
  - Score ALL competing hypotheses together in one LLM call (comparative ACH)
  - Run N temperature-sampled passes; measure per-hypothesis self-consistency
  - Flag low-confidence assessments for human review
  - Output: AssessmentResult[] → Matrix Agent
        ↓
[Tier 3: Matrix Agent]
  - Load the latest snapshot so tallies accumulate across runs
  - Update cumulative tally per hypothesis: ++, +, N/A, -, --
  - Recompute net support; write a versioned CSV snapshot
  - Enforce the storage cap by pruning oldest snapshots
  - Output: versioned ACH matrix snapshots + live result table
```

### Why The Guardian (and not Reuters)?

The project is named for a Reuters-style geopolitical use case, but Reuters' Terms of Use prohibit scraping and its full text is available only via the licensed Reuters Connect platform (see `documentation/Reuters_Delivery_Overview.pdf`). The Guardian's **Open Platform Content API** is the standout free, official alternative that returns the **full article body** with a developer key — so the Scraper Agent sources from it. The architecture is source-agnostic: the agent only emits `ArticleData`, so the source can be swapped.

### Assessment Agent: Comparative ACH Self-Consistency

ACH evidence is diagnostic only insofar as it distinguishes between competing hypotheses, so all hypotheses are evaluated **together**:

1. **Comparative pass**: one LLM call presents the article plus all hypotheses and returns a mark per hypothesis. The prompt instructs that an article not addressing a hypothesis is `N/A` (not weak support), and that mutually exclusive hypotheses shouldn't all get the same positive mark.
2. **Multi-pass sampling**: run N passes (default 10) at `temperature=0.7`.
3. **Self-consistency**: per hypothesis, confidence = fraction of passes agreeing with that hypothesis's majority mark.
   - e.g. 8/10 passes agree on `+` → confidence 0.8; a 5/5 split → 0.5 (ambiguous → flagged).
4. **Cost**: `LLM_NUM_PASSES` calls per article (one comparative call per pass — not per hypothesis). The full article body is sent (Ollama `num_ctx` is set so it isn't truncated).

> **Accuracy note**: directional judgment is bounded by the local model's reasoning. Unstable or low-confidence assessments are surfaced via the human-review flag by design, rather than hidden.

### ACH Matrix

Snapshots accumulate across runs (each run reloads the latest snapshot first):

```
hypothesis_id,Hypothesis,++,+,N/A,-,--,Net Support
h1,China supports US position,5,12,2,1,0,17.0
h2,China maintains neutrality,8,6,3,2,1,14.0
h3,China supports Iran position,2,4,5,10,8,-11.0
```

`Net Support = (++ × 2) + (+ × 1) + (N/A × 0) + (- × −1) + (-- × −2)`. The `hypothesis_id` column lets a snapshot be reloaded into state; `article_count` is recovered as the sum of any hypothesis's tallies.

## Configuration

All settings have defaults (`config/settings.py`) and can be overridden via environment variables or `.env`.

### Hypotheses (`config/hypothesis_config.yaml`)

```yaml
hypotheses:
  - id: "h1"
    name: "China supports US position"
    description: "..."
```

Edit to define different competing hypotheses for other scenarios.

### Domain whitelist (`config/domain_whitelist.txt`)

Only listed domains are fetchable by the Scraper Agent. Default: `content.guardianapis.com` and `theguardian.com`.

### Key environment variables (`.env`)

```bash
# LLM (Ollama)
LLM_MODEL=llama3.1               # must support the configured context window
LLM_ENDPOINT=http://localhost:11434
LLM_NUM_PASSES=10                # self-consistency passes per article
LLM_CONTEXT_WINDOW=8192          # Ollama num_ctx; large enough for full articles

# Article source (The Guardian)
GUARDIAN_API_KEY=test            # 'test' for dev; register a free key for production
GUARDIAN_SECTION=world           # empty string = all sections
GUARDIAN_FROM_DAYS=7             # recency window (0 = disable)
GUARDIAN_ORDER_BY=relevance      # relevance | newest | oldest
SCRAPER_MAX_ARTICLES=25

# Assessment / storage
CONFIDENCE_THRESHOLD=0.6         # flag hypotheses below this confidence
MATRIX_STORAGE_CAP_GB=1.0
ENABLE_DEBUG_LOGGING=false
```

## Development

### Tests

The suite is hermetic — all network/LLM calls are mocked and file I/O uses temp dirs, so it needs no Ollama, Guardian access, or internet:

```bash
uv run pytest                              # run all tests
uv run pytest tests/test_matrix_agent.py   # a single file
uv run pytest -k accumulation              # by keyword
uv run pytest --cov=agents --cov=tools     # with coverage
```

### Adding hypotheses

Edit `config/hypothesis_config.yaml`, then re-run `uv run python main.py`. (Existing matrix snapshots key by `hypothesis_id`; new ids start their tallies fresh.)

### Debug mode

```bash
ENABLE_DEBUG_LOGGING=true uv run python main.py
```

### Checking the GPU

```bash
uv run python -c "import torch; print(torch.cuda.is_available(), torch.cuda.device_count())"
```

## Notes & Known Limitations

- **TLS behind a proxy**: when behind a TLS-inspecting proxy, set/keep `USE_SYSTEM_TRUSTSTORE=true` (default). The scraper verifies HTTPS against the OS trust store via the `truststore` package, keeping verification on without disabling it.
- **Guardian `test` key** is rate-limited and intended for development; register a free production key at <https://open-platform.theguardian.com/>.
- **Model-bounded accuracy**: the assessment is only as good as the local model; low-confidence results are flagged for human review rather than trusted blindly.
- **First run can be slow**: 25 articles × 10 passes over full articles is ~250 LLM calls — smoke-test with reduced settings first.

## Future Enhancements (v2+)

- **Conclusion Agent** — Tree-of-Thought synthesis of matrix snapshots with hypothesis decay weighting
- **Notification Agent** — alerts when conclusions shift beyond a threshold
- **RAG integration** — semantic re-ranking / historical retrieval of article embeddings (`sentence-transformers`)
- **Multi-source ingestion** — combine the Guardian with other compliant sources
- **Web dashboard** — visualize the matrix, manage hypotheses, review flagged items

## Troubleshooting

| Issue | Solution |
|-------|----------|
| `LLM service unavailable` | Ensure Ollama is running and the model is pulled (`ollama list`). Check `LLM_ENDPOINT`. |
| Articles get truncated / poor scoring on long pieces | Use a long-context model (e.g. `llama3.1`) and ensure `LLM_CONTEXT_WINDOW` fits the article. |
| `CERTIFICATE_VERIFY_FAILED` on fetch | Behind a TLS-inspecting proxy — keep `USE_SYSTEM_TRUSTSTORE=true` (default). |
| No new articles found | All matching URLs are already in `data/processed_urls.csv`, or widen `GUARDIAN_FROM_DAYS` / change the query. |
| Run is very slow | Lower `LLM_NUM_PASSES` and/or `SCRAPER_MAX_ARTICLES`. |
| Storage growing | Lower `MATRIX_STORAGE_CAP_GB`; oldest snapshots auto-prune. |

## References

- **ACH Framework**: Richards J. Heuer Jr., *Psychology of Intelligence Analysis*
- **Self-Consistency**: Wei et al., *Self-Consistency Improves Chain of Thought Reasoning in Language Models*
- **The Guardian Open Platform**: <https://open-platform.theguardian.com/>
- **Ollama**: <https://ollama.com>

## License

Academic project — Carnegie Mellon University Agentic AI Certificate Program

---

**Version**: 0.1.0 (July 2026)  
**Status**: v1 complete — three tiers implemented, tested, and verified end-to-end  
**Last Updated**: 2026-06-22

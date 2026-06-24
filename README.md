# Geopolitical ACH Forecasting Agent

**Final Project for CMU Agentic AI Certificate Program (July 2026)**  
**Student**: James Kajdasz  
**Video Demo**: https://youtu.be/ijaKZi1KcTU

## Overview

A **three-tier multi-agent system** that applies **Analysis of Competing Hypotheses (ACH)** to geopolitical news across multiple nations. The system autonomously ingests full-text articles, scores their diagnostic value against per-nation hypotheses on a US-alignment axis, and maintains a versioned evidence matrix for each tracked nation.

Each nation is assessed against three fixed hypotheses:
- **h1**: [Nation] supports the United States
- **h2**: [Nation] maintains a neutral stance with the United States
- **h3**: [Nation] opposes the United States

**Currently tracked nations**: China, Iran, Israel, Qatar, Saudi Arabia, Pakistan, Kuwait, Bahrain

**Key features**:
- 🌍 **Multi-nation**: each nation gets its own independent search, assessment, and ACH matrix
- 🔄 **Linear per-nation pipeline**: Scraper → Assessment → Matrix, one full pass per nation
- 📰 **Full-text sourcing**: articles come from **The Guardian Open Platform Content API** (per-nation query, full article body, free developer key)
- 🧠 **Comparative ACH scoring**: all three hypotheses are scored together in one LLM call so the model discriminates between them; temperature-sampled multi-pass **self-consistency** yields per-hypothesis confidence with human-in-the-loop flagging
- 📊 **Accumulating ACH matrix (Heuer Ch. 8)**: evidence rows (one per article) build up **across runs**, ranked by *inconsistency*, rendered to a color-coded HTML matrix with versioned snapshots
- 📈 **US-alignment line graph**: each nation's HTML includes a time-series chart of cumulative alignment score; a summary page shows all nations together with click-through navigation
- 🔒 **Security-first**: domain whitelisting, no user chat interface, API keys kept out of logs, comprehensive audit logging
- 🖥️ **Live CLI**: streaming progress and a formatted result table per nation (`rich`)
- 🧪 **Tested**: hermetic pytest suite — 86 tests, no network/LLM needed
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
#    llama3.1 (128k context) is the default — it can ingest full articles.
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

A run streams live progress to the terminal and prints the final ACH ranking table for each nation. With 8 nations and default settings (25 articles × 10 passes each), a full run is up to **2,000 LLM calls** — **smoke-test small first**:

```powershell
# PowerShell
$env:SCRAPER_MAX_ARTICLES=3; $env:LLM_NUM_PASSES=2; uv run python main.py
```
```bash
# bash
SCRAPER_MAX_ARTICLES=3 LLM_NUM_PASSES=2 uv run python main.py
```

### What a run does

For each configured nation (in order from `hypothesis_config.yaml`):

1. **Tier 1 — Scraper**: query The Guardian Content API using that nation's search query (e.g. `"Israel United States relations"`); deduplicate against previously processed URLs. Only articles from this nation's search are assessed for this nation.
2. **Tier 2 — Assessment**: for each article, score all three hypotheses together across N temperature-sampled passes; derive per-hypothesis confidence from self-consistency and flag low-confidence results for human review.
3. **Tier 3 — Matrix**: add each article as an evidence row to that nation's ACH matrix (carried over from prior runs), rank hypotheses by inconsistency, and render the color-coded HTML matrix with an embedded US-alignment line graph.

After all nations: write `data/matrix/summary.html` — a multi-line chart of all nations' cumulative scores with click-through navigation to each nation's full matrix.

### Outputs

- Live console: streaming progress + per-nation **hypothesis ranking** (by inconsistency)
- `data/matrix/summary.html` — all-nations overview page; click a nation's line or legend entry to open its detailed matrix
<img width="876" height="473" alt="image" src="https://github.com/user-attachments/assets/0ac0b68f-0834-4f13-8d9f-dc296a68332e" />
- `data/matrix/{nation}/acch_matrix.html` — color-coded ACH matrix for that nation (includes "← Back to Summary" button and US-alignment line graph)
- `data/matrix/{nation}/matrix_state.json` — canonical matrix state reloaded each run
- `data/matrix/{nation}/acch_matrix_v*.html` — timestamped HTML snapshots (audit trail)
- `data/processed_urls.csv` — long-term dedup memory (global across all nations)
- `logs/agent_interactions.log`, `logs/assessments.log`, `logs/errors.log` — audit trail

## Project Structure

```
.
├── main.py                       # Orchestrator + CLI entry point (per-nation loop)
├── agents/
│   ├── base.py                   # Pydantic schemas + per-agent state dataclasses
│   ├── scraper_agent.py          # Tier 1: Guardian ingestion + dedup
│   ├── assessment_agent.py       # Tier 2: comparative ACH self-consistency scoring
│   └── matrix_agent.py           # Tier 3: accumulating ACH matrix + snapshots
├── tools/
│   ├── web_scraper.py            # The Guardian Content API client
│   ├── llm_interface.py          # Ollama client + ACH prompt/parse
│   ├── file_manager.py           # processed-URL dedup + per-nation snapshot pruning
│   ├── audit_logger.py           # file audit logs + rich console logging
│   └── matrix_view.py            # HTML renderer: ACH matrix, line graph, summary page
├── config/
│   ├── settings.py               # Pydantic Settings (env / .env)
│   ├── hypothesis_config.yaml    # nation-keyed hypotheses + search queries
│   └── domain_whitelist.txt      # approved fetch domains
├── tests/                        # hermetic pytest suite (86 tests, mocked I/O)
├── documentation/
│   └── Reuters_Delivery_Overview.pdf   # reference: Reuters Connect (the licensed path)
├── data/                         # runtime, gitignored
│   ├── matrix/
│   │   ├── summary.html          # all-nations overview (generated each run)
│   │   └── {nation}/             # per-nation matrix state + HTML
│   └── processed_urls.csv        # global URL dedup across runs
├── logs/                         # runtime, gitignored (*.log)
├── pyproject.toml                # dependencies + pytest config (uv-managed)
├── .env.template                 # environment configuration template
├── CLAUDE.md                     # guidance for AI coding agents
├── AGENTS.md                     # AI agent development guide
└── README.md                     # this file
```

## Architecture

### Per-Nation Pipeline

```
config/hypothesis_config.yaml
  ↓  (nation loop — one full pass per nation)

[Tier 1: Scraper Agent]
  - Search The Guardian using nation-specific query ("Iran United States relations")
  - Enforce domain whitelist; deduplicate against processed_urls.csv
  - Output: ArticleData[] (only this nation's articles) → Assessment Agent
        ↓
[Tier 2: Assessment Agent]
  - Score all three hypotheses together in one LLM call (comparative ACH)
  - Run N temperature-sampled passes; measure per-hypothesis self-consistency
  - Flag low-confidence assessments for human review
  - Output: AssessmentResult[] → Matrix Agent
        ↓
[Tier 3: Matrix Agent]
  - Maintain evidence-row matrix in data/matrix/{nation}/ accumulating across runs
  - Rank hypotheses by INCONSISTENCY (least evidence against = most likely, Heuer Step 5)
  - Render color-coded HTML matrix with embedded US-alignment line graph
  - Output: data/matrix/{nation}/acch_matrix.html + matrix_state.json
        ↓ (after all nations)
[Summary]
  - Render data/matrix/summary.html: multi-line chart, all nations, click-through nav
```

### Why The Guardian (and not Reuters)?

Reuters' Terms of Use prohibit scraping and its full text is available only via the licensed Reuters Connect platform (see `documentation/Reuters_Delivery_Overview.pdf`). The Guardian's **Open Platform Content API** returns the **full article body** with a free developer key — so the Scraper Agent sources from it. The architecture is source-agnostic: the agent only emits `ArticleData`, so the source can be swapped.

### Assessment Agent: Comparative ACH Self-Consistency

All three hypotheses are evaluated **together** in each LLM pass so the model discriminates between them:

1. **Comparative pass**: one LLM call presents the article + all three hypotheses and returns a mark per hypothesis. The prompt instructs that an article not addressing a hypothesis is `N/A` (not weak support).
2. **Multi-pass sampling**: N passes (default 10) at `temperature=0.7`.
3. **Self-consistency**: per hypothesis, confidence = fraction of passes agreeing with that hypothesis's majority mark.
4. **Cost**: `LLM_NUM_PASSES` calls per article per nation (one comparative call per pass — not per hypothesis).

> **Accuracy note**: judgment is bounded by the local model's reasoning. Low-confidence results are flagged for human review rather than trusted blindly.

### ACH Matrix (Heuer Chapter 8 layout)

Evidence (articles) down the rows, hypotheses across the columns — preserving the per-article audit trail. Each row carries the article's **date**, **confidence**, and a **diagnosticity** flag; rows shown most-recent-first.

```
Date        Article                              H1   H2   H3   Conf  Diag
2026-06-22  Israel-US defence meeting …          ++   N/A  −    83%   ✓
2026-06-21  Israeli PM meets Secretary …         +    N/A  −    90%   ✓
…
```

**Ranking by inconsistency (Step 5):** hypotheses are ranked by an **inconsistency score** (weighted evidence *against*: `−`=1, `−−`=2) — **the most likely hypothesis is the one with the *least* evidence against it, not the most evidence for it.**

State persists as `data/matrix/{nation}/matrix_state.json` (reloaded each run; evidence accumulates, deduped by article id). The viewable result is `data/matrix/{nation}/acch_matrix.html`.

### US-Alignment Line Graph

Each nation's HTML page includes a time-series Canvas chart:

- **X-axis**: article publication date (oldest → newest)
- **Y-axis**: cumulative US-alignment score
- **Scoring per article**: `contribution = weight[h1_mark] − weight[h3_mark]` (h2/neutral contributes 0; weights: `++`=+2, `+`=+1, `N/A`=0, `-`=−1, `--`=−2)
- Line goes **up** when evidence favours h1 (supports US), **down** when evidence favours h3 (opposes US)
- Green fill above zero, red fill below zero; hover tooltip shows date, score, and article title

The summary page (`data/matrix/summary.html`) shows all nations on one chart. Click a line or legend entry to navigate to that nation's full ACH matrix.

## Configuration

All settings have defaults (`config/settings.py`) and can be overridden via environment variables or `.env`.

### Nations & hypotheses (`config/hypothesis_config.yaml`)

```yaml
nations:
  israel:
    search_query: "Israel United States relations"
    hypotheses:
      - id: "h1"
        name: "Israel supports the United States"
        description: "..."
      - id: "h2"
        name: "Israel maintains a neutral stance with the United States"
        description: "..."
      - id: "h3"
        name: "Israel opposes the United States"
        description: "..."
  # add more nations here — no code changes needed
```

**Adding a nation**: add a new entry under `nations:` with a `search_query` and three hypotheses (h1/h2/h3). The pipeline picks it up automatically on the next run and creates `data/matrix/{nation_id}/` automatically.

### Domain whitelist (`config/domain_whitelist.txt`)

Only listed domains are fetchable by the Scraper Agent. Default: `content.guardianapis.com` and `theguardian.com`. No changes needed when adding nations — all searches use the same Guardian API.

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
SCRAPER_MAX_ARTICLES=25          # per nation, per run

# Assessment / storage
CONFIDENCE_THRESHOLD=0.6         # flag hypotheses below this confidence
MATRIX_STORAGE_CAP_GB=1.0        # per-nation snapshot pruning threshold
ENABLE_DEBUG_LOGGING=false
```

## Development

### Tests

The suite is hermetic — all network/LLM calls are mocked and file I/O uses temp dirs:

```bash
uv run pytest                              # run all 86 tests
uv run pytest tests/test_matrix_agent.py   # a single file
uv run pytest -k accumulation              # by keyword
uv run pytest --cov=agents --cov=tools     # with coverage
```

### Debug mode

```bash
ENABLE_DEBUG_LOGGING=true uv run python main.py
```

### Checking the GPU

```bash
uv run python -c "import torch; print(torch.cuda.is_available(), torch.cuda.device_count())"
```

## Notes & Known Limitations

- **TLS behind a proxy**: keep `USE_SYSTEM_TRUSTSTORE=true` (default). The scraper verifies HTTPS against the OS trust store via the `truststore` package.
- **Guardian `test` key** is rate-limited; register a free production key at <https://open-platform.theguardian.com/>.
- **Model-bounded accuracy**: assessment is only as good as the local model; low-confidence results are flagged for human review.
- **Runtime scale**: 8 nations × 25 articles × 10 passes = up to 2,000 LLM calls per run. Smoke-test with `SCRAPER_MAX_ARTICLES=3 LLM_NUM_PASSES=2` first.
- **Summary chart colours**: `_NATION_COLORS` in `tools/matrix_view.py` defines 8 colours. Adding a 9th nation causes colour cycling — add a colour to the list to keep lines distinct.

## Future Enhancements

- **Conclusion Agent** — Tree-of-Thought synthesis of matrix snapshots with hypothesis decay weighting
- **Notification Agent** — alerts when a nation's alignment score crosses a threshold
- **RAG integration** — semantic re-ranking / historical retrieval via `sentence-transformers`
- **Multi-source ingestion** — combine The Guardian with other compliant sources (AP, Reuters Connect)
- **Configurable hypotheses** — allow non-standard hypothesis sets for specific scenarios beyond the US-alignment axis

## Troubleshooting

| Issue | Solution |
|-------|----------|
| `LLM service unavailable` | Ensure Ollama is running and the model is pulled (`ollama list`). Check `LLM_ENDPOINT`. |
| Articles truncated / poor scoring | Use a long-context model (`llama3.1`) and ensure `LLM_CONTEXT_WINDOW` fits the article. |
| `CERTIFICATE_VERIFY_FAILED` | Behind a TLS-inspecting proxy — keep `USE_SYSTEM_TRUSTSTORE=true` (default). |
| No new articles for a nation | All matching URLs already in `data/processed_urls.csv`. Widen `GUARDIAN_FROM_DAYS` or change the search query. |
| Run is very slow | Lower `LLM_NUM_PASSES` and/or `SCRAPER_MAX_ARTICLES`. With 8 nations, even small values add up. |
| Storage growing | Lower `MATRIX_STORAGE_CAP_GB`; oldest snapshots auto-prune per nation. |
| Summary chart lines overlap (same colour) | Two nations sharing a colour — add a colour to `_NATION_COLORS` in `tools/matrix_view.py`. |

## References

- **ACH Framework**: Richards J. Heuer Jr., *Psychology of Intelligence Analysis*
- **Self-Consistency**: Wei et al., *Self-Consistency Improves Chain of Thought Reasoning in Language Models*
- **The Guardian Open Platform**: <https://open-platform.theguardian.com/>
- **Ollama**: <https://ollama.com>

## License

Academic project — Carnegie Mellon University Agentic AI Certificate Program

---

**Version**: 0.3.0 (v3)  
**Status**: v3 complete — multi-nation pipeline, per-nation ACH matrices, US-alignment line graphs, all-nations summary page  
**Last Updated**: 2026-06-23

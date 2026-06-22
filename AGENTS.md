# AI Agent Instructions — Geopolitical ACH Forecasting Agent

Cross-tool guide for AI agents working in this repo. **`CLAUDE.md` is the
detailed, authoritative companion** (architecture, gotchas, file map) and
`README.md` covers setup/usage; keep all three consistent when you change the build.

**Project**: James Kajdasz — CMU Agentic AI Certificate capstone (July 2026).

## What this is

A three-tier, linearly-orchestrated multi-agent system applying **Analysis of
Competing Hypotheses (ACH)** to geopolitical news: **Scraper → Assessment →
Matrix**. It ingests full-text articles, scores their diagnostic value against
competing hypotheses, and maintains a versioned evidence matrix (e.g. China's
likely position in a US–Iran conflict).

**Status**: v1 complete — all three tiers implemented, a hermetic pytest suite
in `tests/`, and verified end-to-end against Ollama + `llama3.1`.

## Tech stack (what's actually used)

| Component | Role |
|-----------|------|
| **requests + The Guardian Content API** | Full-text article sourcing (free developer key) |
| **Ollama** (default `llama3.1`) over HTTP | Local LLM for assessment |
| **pydantic / pydantic-settings** | State schemas + configuration |
| **truststore** | TLS via the OS trust store (works behind a TLS-inspecting proxy) |
| **rich** | Live console logging + the result table |
| **pytest** | Hermetic test suite |

**Not used despite being installed**: `langgraph`/`langchain` (orchestration is
plain sequential Python in `main.py`, not a state graph). `torch` /
`transformers` / `sentence-transformers` are present for GPU/v2 work, but the
runtime LLM path is the Ollama HTTP API, not local transformers.

## Environment & commands

- **Python 3.13**, managed by **`uv`** (`.venv`).
- Ollama with a **long-context** model (`ollama pull llama3.1`); on Windows it
  runs as a background service after install.

```bash
uv sync                      # install deps
uv run python main.py        # run the pipeline (live console + matrix table)
uv run pytest                # hermetic tests (no network/LLM needed)
uv run --with ruff ruff check .   # lint
```

## Architecture (current)

1. **Scraper** (`agents/scraper_agent.py` + `tools/web_scraper.py`) — queries the
   Guardian API for full-body articles, enforces `config/domain_whitelist.txt`,
   dedups against `data/processed_urls.csv`, and emits `ArticleData`. The API key
   is passed via request params so it never lands in logs.
2. **Assessment** (`agents/assessment_agent.py` + `tools/llm_interface.py`) —
   **comparative ACH**: all hypotheses are scored together in one Ollama call per
   pass; `LLM_NUM_PASSES` passes give per-hypothesis self-consistency confidence;
   results below `confidence_threshold` are flagged. The full article body is sent
   (Ollama `num_ctx` set so it isn't truncated). Cost = `LLM_NUM_PASSES` calls per
   article (not × hypotheses).
3. **Matrix** (`agents/matrix_agent.py`) — reloads the latest snapshot so tallies
   **accumulate across runs**, recomputes net support (`++/+/N/A/-/--` =
   +2/+1/0/−1/−2), writes a versioned CSV snapshot (with a `hypothesis_id`
   column), and prunes oldest snapshots past `matrix_storage_cap_gb`.

`agents/base.py` holds the Pydantic schemas that are the contract between tiers.

## Conventions & constraints

- **Config flows through `Settings`** — agents/tools take a `config` object in
  `__init__` and read values off it; don't re-read env vars ad hoc.
- **Local LLM only** — no external LLM APIs. `LLMInterface` verifies Ollama on init.
- **No user chat interface** (prompt-injection avoidance) — inputs are config
  files + fetched article content.
- **Keep secrets out of logs** — pass API keys via `requests` params, not URLs.
- **Logging** — file audit logs via `AuditLogger` helpers (`tools/audit_logger.py`)
  plus a `rich` console handler; `main.py` prints the final matrix table.
- **Tests stay hermetic** — mock network/LLM, use `tmp_path` for filesystem; never
  hit Ollama or the Guardian in tests.

## Pitfalls

- **Use a long-context model** (e.g. `llama3.1`) or Ollama truncates long articles.
- **Preserve the comparative prompt's relevance gate** — scoring hypotheses in
  isolation makes the model over-affirm them; the single-call comparative prompt
  and the explicit "not relevant → N/A" rule are what fix it.
- **Matrix accumulates** — deleting `data/matrix/` resets the evidence tally;
  `data/processed_urls.csv` deduplicates scraping across runs.

## Future (v2+)

Conclusion Agent (synthesis), Notification Agent (threshold alerts), RAG /
semantic re-ranking, multi-source ingestion, web dashboard. See README.

---

**Last Updated**: 2026-06-22 · **Project Version**: 0.1.0

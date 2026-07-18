# Orbit

**Adaptive Daily Learning Engine.** A provider-agnostic, config-driven CLI that generates personalized daily learning sessions with an LLM, tracks your performance, and adapts using spaced repetition and competence-based topic prioritization. A subject is a swappable prompt file — same engine, any domain.

> Status: **Phase 1** (subject files + session generation). Running `python main.py` generates a full 5-item learning session for the active track. Later phases add interactive scoring, persistence, the adaptive engine, and scheduling.

---

## Requirements

- Python 3.10+
- [Poetry](https://python-poetry.org/docs/#installation) for dependency management
- One of:
  - [Ollama](https://ollama.com/download) for local, free, GPU-accelerated inference **(default)**
  - Or an API key from Anthropic / OpenAI / Google / Groq

## Setup

```bash
# 1. Install dependencies into a Poetry-managed venv
poetry install

# 2. Optional: put the venv inside the project so your IDE finds it easily
poetry config virtualenvs.in-project true --local
poetry install                                # reruns using the local venv

# 3. Copy the env template (leave keys blank if you're using Ollama)
cp .env.example .env
```

## Running with Ollama (default, local, free)

```bash
# Install Ollama once from https://ollama.com/download, then:
ollama serve &                                # background daemon on :11434
ollama pull llama3.1:8b                       # matches the default in config.yaml

# Run the hello-world
poetry run python main.py
```

That's it — no API keys, no billing, your GPU does the work. Change `model:` in `config.yaml` to any Ollama tag you've pulled (`qwen2.5:14b`, `mistral:7b`, `llama3.2:3b`, etc.).

## Running with a hosted API (occasional / higher quality)

Edit `config.yaml`, comment out the Ollama `model:` line, and uncomment one of the alternatives:

```yaml
# model: "ollama/llama3.1:8b"
model: "anthropic/claude-sonnet-4-5"
```

Then set the matching key in `.env`:

```bash
# .env
ANTHROPIC_API_KEY=sk-ant-...
```

Run the same way:

```bash
set -a && source .env && set +a
poetry run python main.py
```

**Where to get API keys** (all separate accounts from claude.ai / Pro subscriptions):

| Provider | Console URL | Notes |
|---|---|---|
| Anthropic | https://console.anthropic.com | Pay-as-you-go; **not** included in Claude Pro |
| OpenAI | https://platform.openai.com | Pay-as-you-go |
| Google Gemini | https://aistudio.google.com/app/apikey | Free tier available |
| Groq | https://console.groq.com | Generous free tier |

Switching providers is always: **one line in `config.yaml` + one key in `.env`**. No code changes.

## Swapping subjects

Change `active_track:` in `config.yaml` to any track defined in the `tracks:` block. Two ship with the repo:

- `ml_interview` → `subjects/ml_interview.md` (ML/DL interview prep)
- `spanish_b2` → `subjects/spanish_b2.md` (Spanish B2 fluency)

Adding a track = write a new `subjects/<name>.md` in the same format + add an entry under `tracks:`. No code changes.

Every session is displayed in the terminal via Rich and saved as a markdown file at `output/<track>/<date>.md` for later reference.

## Repo layout (current)

```
orbit-learn/
├── config.yaml           # User configuration (safe to commit; no secrets)
├── main.py               # Phase 1 entry point: load, generate, display, save
├── pyproject.toml        # Poetry-managed deps and project metadata
├── .env.example          # Template for provider API keys
├── src/
│   ├── config.py         # Loads and validates config.yaml (Pydantic)
│   ├── models.py         # SubjectConfig, ItemAssignment, Item, Session
│   ├── provider.py       # The ONLY module that imports litellm
│   ├── session.py        # Build prompt → call LLM → parse JSON → Session
│   └── subject.py        # Parse subject prompt files → SubjectConfig
├── subjects/
│   ├── ml_interview.md
│   └── spanish_b2.md
├── data/                 # (Phase 2) SQLite state, gitignored
├── output/               # Generated session markdown, gitignored
└── docs/design_doc_v1.0.0.md
```

## Design principles

- **No framework bloat.** No LangChain, no LangGraph, no agent platforms. Every component is small and purpose-built.
- **Provider-agnostic from day one.** One LiteLLM adapter, any backend — local Ollama, Anthropic, OpenAI, Gemini, Groq, LM Studio.
- **Config over code.** Changing the subject, model, delivery method, or schedule never requires editing Python.
- **Prompt files are the product.** A subject file (`subjects/*.md`) fully defines what and how the engine teaches. The engine is generic; the prompt file is specific.
- **Adaptation is deterministic.** The LLM generates content. Python code makes all curriculum decisions.
- **Local-first.** SQLite for state. Everything runs on one machine until you opt into scheduled delivery.

See [`docs/design_doc_v1.0.0.md`](docs/design_doc_v1.0.0.md) for the full architecture and phased plan.

## Roadmap

| Phase | Adds |
|---|---|
| 0 ✅ | Skeleton, config loader, LiteLLM provider adapter (Ollama + hosted APIs), hello world |
| 1 ✅ | Subject file parser (ml_interview + spanish_b2), Pydantic session models, JSON-mode LLM call with retries, Rich terminal display, markdown session save |
| 2 | SQLite persistence, `orbit learn` interactive CLI, `orbit status`, `orbit history` |
| 3 | Adaptive scoring, spaced repetition, remediation, `orbit calibrate` |
| 4 | Delivery methods (terminal / markdown / email), scheduling via cron or GitHub Actions |
| 5 | Multi-track, bundled subjects, dashboard, `orbit summary`, `orbit export`, polish |

## License

MIT (added in Phase 5).

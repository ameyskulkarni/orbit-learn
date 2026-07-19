# 🛰️ Orbit

**A personal LLM tutor in your terminal.** Config-driven, adaptive, local-first.
Study anything — daily.

<div align="center">

[![Python](https://img.shields.io/badge/python-3.10%2B-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)
[![Tests](https://img.shields.io/badge/tests-37%20passing-brightgreen.svg)](tests/)
[![Local First](https://img.shields.io/badge/local--first-Ollama-orange.svg)](https://ollama.com)
[![Providers](https://img.shields.io/badge/providers-Ollama%20%7C%20Anthropic%20%7C%20OpenAI%20%7C%20Gemini%20%7C%20Groq-blueviolet.svg)](https://github.com/BerriAI/litellm)
![No frameworks](https://img.shields.io/badge/no%20LangChain-yes-ff69b4.svg)

*One focused session a day. Weak topics come back sooner. Mastered ones drift out. Nothing to remember — the engine remembers for you.*

</div>

---

## What is this?

Orbit generates a **5-item personalized learning session** every day using an LLM you choose, tracks how well you answered, and picks tomorrow's session based on what you know and don't know. A **subject is a swappable markdown file** — same engine, any domain.

Runs locally on Ollama by default (free, private, GPU-accelerated). One config line switches to Anthropic / OpenAI / Gemini / Groq when you want higher quality.

```
── 3/5  Topic: attention_mechanisms  |  ★★★☆☆  |  conceptual  |  teach_then_practice ──

📖 TEACH:
Attention lets a model focus on relevant parts of the input rather than treating
all positions equally. Think of it as a soft lookup: Query asks "what am I
looking for?", Keys say "here is what I contain", Values provide the content.
The scaling factor 1/√d_k prevents softmax saturation. Common trap: attention
is O(n²) in sequence length — interviewers love asking when this matters.

📝 QUESTION:
Explain what multi-head attention adds over single-head attention and give a
concrete example of what different heads might learn.

Your answer (Enter to skip): ▌
```

---

## ⚡ Quickstart (2 minutes)

Local, free, private — powered by [Ollama](https://ollama.com):

```bash
# 1. Install Ollama and pull a model
brew install ollama                       # or download at ollama.com/download
ollama pull qwen2.5:32b-instruct          # any capable model works

# 2. Clone Orbit
git clone git@github.com:ameyskulkarni/orbit-learn.git
cd orbit-learn
poetry install                            # requires Python 3.10+ and Poetry

# 3. Sanity check + seed the engine
poetry run orbit init                     # verifies everything is wired up
poetry run orbit calibrate                # a quick 5-item baseline
poetry run orbit learn                    # 🚀 your first real session
```

You're now learning ML interview prep. Change `active_track` in `config.yaml` to swap subjects. Add a new track by writing a markdown file. **No Python edits.**

> **Prefer a hosted API?** In `config.yaml`, comment the Ollama `model:` line and uncomment one of the alternatives (Gemini's `flash` tier is free). Then set the matching key in `.env`.

---

## 🎯 Why Orbit?

| | |
|---|---|
| **🎯 Adaptive** | EWMA competence per topic. Pluggable scheduling: choose Leitner (default), SM-2, or FSRS-4.5 per track. Weak topics come back sooner, mastered ones drift out, failed ones get a teaching block at reduced difficulty. |
| **🧠 Config-driven** | Change the subject with one line. Change the model with one line. Change the delivery method with one line. Zero code. |
| **🔒 Local by default** | Runs on your GPU via Ollama. No API key, no cloud, no lock-in. Your learning history stays on your machine. |
| **🔌 Provider-agnostic** | Ollama, Anthropic, OpenAI, Gemini, Groq — one adapter, [LiteLLM](https://github.com/BerriAI/litellm) under the hood. |
| **📦 No framework bloat** | Zero LangChain. Zero vector DBs. 12 modules, 37 unit tests, 6 dependencies. Read the whole thing in an afternoon. |
| **⏰ Learns overnight** | Cron or GitHub Actions delivers your session. Score with `orbit score` when you have coffee. |
| **📝 Prompt files are the product** | A subject file is a soft program: SUBJECT + TOPICS + DIFFICULTY_LEVELS + TEACHING_STYLE + GRADING_RUBRIC. Fork and share. |

---

## 📚 Subjects that ship with Orbit

| Track | For | Topics | File |
|---|---|---|---|
| `ml_interview` | ML/DL engineer interviews (FAANG-level) | 18 | [subjects/ml_interview.md](subjects/ml_interview.md) |
| `system_design` | Senior / staff system-design loops | 20 | [subjects/system_design.md](subjects/system_design.md) |
| `python_fundamentals` | Deep Python — mutability, GIL, asyncio, packaging | 20 | [subjects/python_fundamentals.md](subjects/python_fundamentals.md) |
| `sql_mastery` | Intermediate → advanced SQL, PostgreSQL-flavored | 20 | [subjects/sql_mastery.md](subjects/sql_mastery.md) |
| `spanish_b2` | Spanish B1 → B2 conversational fluency | 18 | [subjects/spanish_b2.md](subjects/spanish_b2.md) |

**Bring your own** — one markdown file, seven fields, no code. See [CONTRIBUTING.md](CONTRIBUTING.md#contributing-a-new-subject).

---

## 🛠️ Commands

```
orbit init                       Verify config, subject files, provider connectivity
orbit calibrate                  Seed the adaptive engine (first-run baseline)
orbit learn                      Interactive daily session
orbit run                        Unattended (cron / GitHub Actions)
orbit score [id]                 Score a delivered session (email / markdown workflow)
orbit status                     Per-topic competence, streaks, next review
orbit history                    Recent sessions and averages
orbit dashboard                  Visual dashboard (bars + sparkline + reviews)
orbit summary                    Weekly digest across all tracks
orbit export --format csv|json   Export everything to CSV or JSON
```

Every command takes `--track/-t <name>` to target a specific track. Defaults to `active_track` in config.

### Dashboard preview

```
Orbit — Machine Learning & Deep Learning Interview Preparation
Track: ml_interview   Sessions: 1   Difficulty: 3.04/5   🔥 1-day streak

╭──────────────────────────── Difficulty over time ─────────────────────────────╮
│ ▄▄▅▅▆▆▆▇▇   3.0 → 3.6   (9 sessions)                                          │
╰───────────────────────────────────────────────────────────────────────────────╯
╭────────────────────────────── Topic competence ───────────────────────────────╮
│  Topic                       Competence     Score  Seen  Streak               │
│  dropout_and_regularization  █████░░░░░░░  2.00/5     1       0               │
│  backpropagation             ███████░░░░░  3.00/5     1       0               │
│  loss_functions              ███████░░░░░  3.00/5     1       0               │
│  batch_normalization         ██████████░░  4.00/5     1       1               │
│  attention_mechanisms        ████████████  5.00/5     1       1               │
╰───────────────────────────────────────────────────────────────────────────────╯
╭─────────────────────────── Upcoming reviews (14d) ────────────────────────────╮
│  When              Topic                       Competence  Interval           │
│  tomorrow          backpropagation                 3.00/5        1d           │
│  tomorrow          dropout_and_regularization      2.00/5        1d           │
│  2026-07-20 (+2d)  attention_mechanisms            5.00/5        2d           │
│  2026-07-20 (+2d)  batch_normalization             4.00/5        2d           │
╰───────────────────────────────────────────────────────────────────────────────╯
```

---

## 🔁 How adaptation works

```
      ┌──────────────────┐
      │  You score 1-5   │
      └────────┬─────────┘
               ↓
      ┌────────────────────────────────────────────┐
      │  Update EWMA competence per topic  (α=0.3) │
      │  Update review interval (Leitner)          │
      │  Adjust track difficulty (+0.2 / −0.3)     │
      │  Flag remediation if score < 2             │
      └────────┬───────────────────────────────────┘
               ↓
      ┌────────────────────────────────────────────┐
      │  Rank all topics by priority:              │
      │    +0.35·weakness                          │
      │    +0.25·recency                           │
      │    +0.25·review-urgency                    │
      │    +0.10·novelty                           │
      │    −0.05·fatigue                           │
      │    +0.50 if remediation                    │
      └────────┬───────────────────────────────────┘
               ↓
      ┌────────────────────────────────────────────┐
      │  Top-N by priority → next session          │
      │  Each item gets:                           │
      │    mode = teach_then_practice | practice   │
      │           | review                         │
      │    difficulty = round(track_diff) −1 rem   │
      └────────┬───────────────────────────────────┘
               ↓
      ┌────────────────────────────────────────────┐
      │  LLM generates the item (question, teach,  │
      │  expected answer). You score.  Loop.       │
      └────────────────────────────────────────────┘
```

The LLM never picks what to teach — the scoring engine does. The LLM only decides **how to express** each item, guided by your subject file's teaching style and rubric. That's why swapping providers doesn't change your curriculum, and why the engine is provider-agnostic.

**All the tuning knobs** (weights, α, intervals, difficulty steps) live at the top of [`orbit_learn/scoring.py`](orbit_learn/scoring.py). Change with confidence — 37 unit tests cover the math.

---

## 🔀 Swap the model with one line

```yaml
# config.yaml
model: "ollama/qwen2.5:32b-instruct"     # local, free, GPU
# model: "anthropic/claude-sonnet-4-5"   # highest quality
# model: "openai/gpt-4o"                 # OpenAI
# model: "gemini/gemini-1.5-flash"       # free tier
# model: "groq/llama-3.1-70b-versatile"  # free tier, fast
```

Set the matching env var in `.env` (`ANTHROPIC_API_KEY=...`, `GEMINI_API_KEY=...`, etc.). No code changes. LiteLLM routes to the right SDK based on the prefix.

**Where to get API keys** (all separate accounts from claude.ai / ChatGPT Plus / any subscription):

| Provider | Console | Notes |
|---|---|---|
| Anthropic | https://console.anthropic.com | Pay-as-you-go; not included in Claude Pro |
| OpenAI | https://platform.openai.com | Pay-as-you-go |
| Google Gemini | https://aistudio.google.com/app/apikey | Generous free tier |
| Groq | https://console.groq.com | Generous free tier |

---

## 📨 Delivery + scheduling

Three ways for a generated session to reach you:

| Method | What it does | Best for |
|---|---|---|
| `terminal` | Prints in your terminal | Local, interactive |
| `markdown` | Writes `output/<track>/<date>.md` | Cron; read on your phone |
| `email` | SMTP (STARTTLS 587); plain + HTML | Push notification; unattended |

Set `delivery.method` in `config.yaml` or override once with `orbit run --method markdown`. Add a Slack / Telegram / GitHub-Issues delivery in ~30 lines by implementing the `Delivery` protocol in [`orbit_learn/delivery.py`](orbit_learn/delivery.py) — see [CONTRIBUTING.md](CONTRIBUTING.md#adding-a-delivery-method).

### Run it on a schedule

**Local cron:**
```
0 8 * * * cd ~/orbit-learn && ~/.local/bin/poetry run orbit run >> ~/orbit.log 2>&1
```

**GitHub Actions:** the included workflow at [`.github/workflows/daily_session.yml`](.github/workflows/daily_session.yml) fires at 08:00 UTC daily, runs `orbit run`, and commits the updated `data/*.db` back to the repo. Use a **private repo** — your learning history is stored as plaintext. GitHub Actions runners can't reach local Ollama, so switch `model:` to a hosted API and add the matching key as a repo secret.

**Deferred scoring:** whichever way it's delivered, run `orbit score` when you have time — no args picks up the newest unscored session automatically.

---

## 🏗️ Architecture

```
orbit-learn/
├── config.yaml                 # User configuration
├── subjects/                   # Prompt files — the swappable unit
│   ├── ml_interview.md
│   ├── system_design.md
│   ├── python_fundamentals.md
│   ├── sql_mastery.md
│   └── spanish_b2.md
├── orbit_learn/
│   ├── cli.py                  # Typer CLI — all `orbit *` commands
│   ├── config.py               # Pydantic config loader
│   ├── subject.py              # YAML-in-markdown subject parser
│   ├── models.py               # SubjectConfig, Session, Item, ItemAssignment
│   ├── scoring.py              # EWMA, priority, mode selection, difficulty
│   ├── scheduler.py            # Spaced repetition intervals
│   ├── session.py              # Prompt build → LLM call → JSON parse
│   ├── provider.py             # THE ONLY module that imports litellm
│   ├── persistence.py          # SQLite: sessions, items, topic_stats, calibration
│   ├── delivery.py             # Terminal / Markdown / Email (pluggable)
│   ├── display.py              # Shared Rich rendering
│   └── dashboard.py            # Rich-based visual dashboard
├── tests/                      # Pure-function tests (37, run in < 100ms)
├── data/                       # One SQLite DB per track (gitignored)
├── output/                     # Generated session markdown (gitignored)
└── .github/workflows/          # Daily cron workflow
```

**Design principles**
- **No frameworks for framework's sake.** No LangChain, LangGraph, agent platforms.
- **Provider-agnostic from day one.** Every LLM call goes through `provider.complete()`.
- **Adaptation is deterministic.** The LLM generates content; Python decides curriculum.
- **Local-first.** SQLite for state. Everything runs on one machine until you opt into scheduled delivery.

Read the full design in [`docs/design_doc_v1.0.0.md`](docs/design_doc_v1.0.0.md).

---

## 🧪 Tests

```bash
poetry run pytest -v                      # 37 tests, ~50ms, pure functions
poetry run pytest --cov=orbit_learn       # with coverage
```

Tests target the adaptive engine: EWMA update, difficulty adjustment formula, priority weighting, mode selection, remediation state, spaced-repetition interval progression, review-urgency ramp. Deterministic and LLM-free.

---

## 🤝 Contributing

This project welcomes contributions of every size:

- **Write a subject file.** The highest-leverage contribution. See [CONTRIBUTING.md](CONTRIBUTING.md).
- **Add a delivery method.** Slack, Telegram, GitHub Issues, Discord — one class each.
- **Improve the scoring engine.** SM-2 or FSRS strategies are on the roadmap; write tests first.
- **File a bug.** With `orbit init` output + your `config.yaml` (redacted).

Ways to say hi: open an issue, drop a PR, or star the repo if you like where it's going. 🙏

---

## 🗺️ Roadmap

- [x] Phase 0-2 — CLI + persistence + provider abstraction
- [x] Phase 3 — Adaptive engine (EWMA + spaced repetition + remediation)
- [x] Phase 4 — Pluggable delivery + scheduling
- [x] Phase 5 — Multi-track polish + dashboard + bundled subjects
- [x] SM-2 / FSRS scheduling strategies (Phase 6 — [design doc §16](docs/design_doc_v1.0.0.md#16-pluggable-scheduling-strategies-phase-6-detailed-design))
- [ ] Slack / Telegram / Discord delivery adapters
- [ ] Voice mode (STT for language tracks)
- [ ] Collaborative subject registry
- [ ] Optional local web UI

---

## 📜 License

MIT. See [LICENSE](LICENSE).

---

## 💡 Inspiration

Orbit is named after its core mechanic: **topics orbit back to you on a schedule.** Weak topics orbit close (short intervals). Mastered topics drift to wider orbits. Eventually, retained knowledge escapes orbit entirely.

Built on the shoulders of decades of spaced-repetition research (Ebbinghaus, Leitner, SuperMemo, FSRS) and modern LLMs. Simple where it can be, principled where it matters.

<div align="center">

*If Orbit teaches you something useful, please ⭐ the repo and share your subject files.*

</div>

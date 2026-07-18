# Orbit — Design Document

**Adaptive Daily Learning Engine**
**Version:** 1.0
**Date:** July 2026

---

## 1. Vision

Orbit is a provider-agnostic, config-driven CLI tool that generates personalized daily learning sessions using LLMs, tracks learner performance, and adapts content using spaced repetition and competence-based topic prioritization. A subject is a swappable prompt file — same engine, any domain.

The name comes from the core mechanic: topics orbit back to you on a schedule. Weak topics orbit close (short intervals). Mastered topics drift to wider orbits. Eventually, retained knowledge escapes orbit entirely.

---

## 2. Core Principles

- **No frameworks for framework's sake.** No LangChain, no LangGraph, no agent platforms. Every component is purpose-built, readable, and explainable.
- **Provider-agnostic from day one.** All model calls go through a single adapter using LiteLLM. Switching providers means changing one config line and one env var.
- **Config-driven, not code-driven.** Changing the subject, model, delivery method, or schedule never requires editing Python.
- **Prompt files are the product.** A subject prompt file is a soft program that fully defines what and how the system teaches. The engine is generic; the prompt file is specific.
- **Adaptation is deterministic.** The LLM generates content. Python code makes all curriculum decisions (topic selection, difficulty, session composition). The LLM never decides what to teach — it only decides how to express it.
- **Local-first.** SQLite for state. No cloud services required. Everything runs on one machine until the user opts into scheduled delivery.

---

## 3. Architecture Overview

```
┌─────────────────────────────────────────────────────────────┐
│                        CLI (Typer)                          │
│   orbit init | orbit learn | orbit status | orbit export    │
└────────────┬──────────────┬──────────────┬──────────────────┘
             │              │              │
     ┌───────▼───────┐  ┌──▼───────┐  ┌───▼────────┐
     │ Session       │  │ Scoring  │  │ Dashboard  │
     │ Generator     │  │ Engine   │  │ & Reports  │
     └───────┬───────┘  └──┬───────┘  └───┬────────┘
             │             │              │
     ┌───────▼─────────────▼──────────────▼────────┐
     │              Persistence (SQLite)            │
     └───────┬─────────────────────────────────────┘
             │
     ┌───────▼───────┐     ┌──────────────────┐
     │   Provider    │────▶│ LiteLLM          │
     │   Adapter     │     │ (any LLM)        │
     └───────────────┘     └──────────────────┘
```

### Component Map

| Component | File | Responsibility |
|---|---|---|
| CLI | `src/cli.py` | User-facing commands, interactive session flow |
| Config | `src/config.py` | Load and validate `config.yaml` |
| Provider Adapter | `src/provider.py` | Single function for all LLM calls via LiteLLM |
| Subject Loader | `src/subject.py` | Parse subject prompt files into structured data |
| Session Generator | `src/session.py` | Build prompts, call LLM, parse structured session output |
| Scoring Engine | `src/scoring.py` | Competence scores, difficulty adjustment, topic prioritization |
| Spaced Repetition | `src/scheduler.py` | Interval calculation, review scheduling |
| Persistence | `src/persistence.py` | SQLite read/write for all state |
| Delivery | `src/delivery.py` | Terminal, markdown file, email output |
| Dashboard | `src/dashboard.py` | Terminal-based progress visualization |

---

## 4. Config Schema

```yaml
# config.yaml

# --- Provider ---
model: "anthropic/claude-sonnet-4-5"  # LiteLLM model string
# Set the matching API key as an env var (e.g., ANTHROPIC_API_KEY)
# No secrets in this file.

# --- Active Track ---
active_track: "ml_interview"  # Name of the track to run (matches subjects/<name>.md)

# --- Tracks ---
# Each track has its own subject file, state, and settings.
# Adding a track = adding a subject file + an entry here.
tracks:
  ml_interview:
    subject_file: "subjects/ml_interview.md"
    items_per_session: 5
    scoring_strategy: "ewma"         # Options: ewma | sm2 | fsrs (future)
    enable_llm_judge: false           # LLM-as-judge scoring (costs extra API calls)
  spanish_b2:
    subject_file: "subjects/spanish_b2.md"
    items_per_session: 5
    scoring_strategy: "ewma"
    enable_llm_judge: false

# --- Delivery ---
delivery:
  method: "terminal"                  # Options: terminal | markdown | email
  # Email settings (only needed if method is "email")
  # email:
  #   smtp_host: "smtp.gmail.com"
  #   smtp_port: 587
  #   from: "orbit@example.com"
  #   to: "learner@example.com"
  #   # Password via env var: ORBIT_EMAIL_PASSWORD

# --- Schedule ---
schedule:
  enabled: false
  time: "08:00"                       # 24h local time
  method: "cron"                      # Options: cron | github_actions
```

---

## 5. Subject Prompt File Format

Every subject is a single markdown file. This is the swappable unit — the engine reads it, the LLM uses it, and the learner never touches Python.

```markdown
# subjects/ml_interview.md

SUBJECT: Machine Learning & Deep Learning Interview Preparation
LEARNER_CONTEXT: ML engineer with 2-3 years experience, preparing for
  FAANG-level interviews. Comfortable with basics, needs depth on
  system design and edge cases.

SESSION_SHAPE:
  - conceptual: 1        # "Explain X" / "Compare A vs B"
  - applied: 1            # "Given this scenario, what would you do?"
  - coding: 1             # "Implement X" / "Write the gradient update for Y"
  - system_design: 1      # "Design a recommendation system for Z"
  - debugging: 1           # "You observe X in prod. Diagnose."

TOPICS:
  - backpropagation
  - attention_mechanisms
  - batch_normalization
  - dropout_and_regularization
  - loss_functions
  - optimizers
  - cnn_architectures
  - rnn_lstm_gru
  - transformers
  - transfer_learning
  - data_augmentation
  - feature_engineering
  - bias_variance
  - evaluation_metrics
  - recommendation_systems
  - model_serving
  - ab_testing_for_ml
  - distributed_training

DIFFICULTY_LEVELS:
  1: Recognition and recall. "What is X?" / "Name the components of Y."
  2: Comprehension. "Explain why X works." / "Compare A and B."
  3: Application. "Given this situation, apply X." / "Implement a basic version."
  4: Analysis. "Why might X fail here?" / "Derive the gradient for this layer."
  5: Synthesis. "Design a system that uses X, Y, Z together." / "Propose an improvement to X and justify it."

TEACHING_STYLE: |
  When teaching a topic (remediation or first introduction):
  - Lead with intuition: one sentence on WHY this exists, what problem it solves.
  - Give one concrete, minimal example (prefer numeric/visual over abstract).
  - State the key formula or algorithm step in plain language, then in notation.
  - End with one common misconception or interview trap.
  Keep teaching blocks to 4-6 sentences. Dense, not verbose.

GRADING_RUBRIC: |
  1 - Blank or fundamentally wrong.
  2 - Vague or partially correct; missing key concepts.
  3 - Correct core idea but incomplete or imprecise.
  4 - Solid answer, covers edge cases, would pass an interview round.
  5 - Exceptional. Demonstrates deep understanding, gives nuance an
      interviewer wouldn't expect.
```

### Rules for Subject Files

- All fields are required. The engine validates on load and gives clear errors.
- TOPICS must be a flat list of snake_case strings. These are the atom-level units the scoring engine tracks.
- SESSION_SHAPE item types are defined by the subject file, not the engine. The engine passes them to the LLM as-is. This keeps the engine generic.
- DIFFICULTY_LEVELS maps integers 1–5 to descriptions. The engine sends the current difficulty level for each topic; the LLM uses these descriptions to calibrate item complexity.
- TEACHING_STYLE tells the LLM how to teach when the engine requests a teaching block (for remediation or new topic introduction).
- GRADING_RUBRIC is shown to the learner after each item AND sent to the LLM if LLM-as-judge is enabled.

---

## 6. Database Schema

SQLite. One database file per track at `data/<track_name>.db`.

```sql
-- The source of truth for all learning state.

CREATE TABLE sessions (
    id          TEXT PRIMARY KEY,     -- UUID
    track       TEXT NOT NULL,
    date        TEXT NOT NULL,        -- ISO date (YYYY-MM-DD)
    created_at  TEXT NOT NULL,        -- ISO datetime
    difficulty  REAL NOT NULL,        -- Global difficulty level at session start (1.0-5.0)
    raw_json    TEXT                  -- Full LLM-generated session for debugging/replay
);

CREATE TABLE items (
    id              TEXT PRIMARY KEY,     -- UUID
    session_id      TEXT NOT NULL REFERENCES sessions(id),
    topic           TEXT NOT NULL,        -- Matches TOPICS list in subject file
    item_type       TEXT NOT NULL,        -- Matches SESSION_SHAPE keys (conceptual, applied, etc.)
    difficulty      INTEGER NOT NULL,     -- Difficulty level this item was generated at (1-5)
    question        TEXT NOT NULL,
    expected_answer TEXT,
    user_score      INTEGER,             -- Self-score 1-5 (NULL until scored)
    llm_judge_score INTEGER,             -- LLM-as-judge score 1-5 (NULL if disabled)
    user_answer     TEXT,                -- Free-text user answer (optional)
    scored_at       TEXT,                -- ISO datetime when scored
    FOREIGN KEY (session_id) REFERENCES sessions(id)
);

CREATE TABLE topic_stats (
    -- Derived/cached. Recomputed after each session.
    track           TEXT NOT NULL,
    topic           TEXT NOT NULL,
    competence      REAL NOT NULL DEFAULT 0.0,  -- Rolling competence score (0.0-5.0)
    times_seen      INTEGER NOT NULL DEFAULT 0,
    times_correct   INTEGER NOT NULL DEFAULT 0, -- Score >= 4 counts as correct
    last_seen       TEXT,                        -- ISO datetime
    current_streak  INTEGER NOT NULL DEFAULT 0, -- Consecutive sessions with score >= 4
    next_review     TEXT,                        -- ISO date: when spaced repetition says to revisit
    review_interval REAL NOT NULL DEFAULT 1.0,  -- Current interval in days
    PRIMARY KEY (track, topic)
);

CREATE TABLE calibration (
    -- Stores initial calibration results (Phase 3+)
    track           TEXT NOT NULL,
    topic           TEXT NOT NULL,
    initial_score   INTEGER NOT NULL,
    calibrated_at   TEXT NOT NULL,
    PRIMARY KEY (track, topic)
);
```

---

## 7. Scoring Engine — Detailed Design

### 7.1 Competence Score (per topic)

Exponentially Weighted Moving Average (EWMA) of scores for that topic.

```
competence_new = alpha * latest_score + (1 - alpha) * competence_old
```

- `alpha = 0.3` (weighs recent performance heavily but doesn't erase history)
- Cold-start: first score on a topic becomes the initial competence.
- A score of 4+ counts as "correct" for streak tracking.

**Future upgrade:** SM-2, FSRS. The scoring strategy is selected in config and loaded via a strategy pattern. The EWMA implementation is the default. SM-2 and FSRS implement the same interface.

### 7.2 Topic Priority (determines what appears in next session)

Before each session, compute priority for every topic in the subject file:

```
priority(topic) = w1 * (1.0 - competence / 5.0)      # Weakness boost
                + w2 * days_since_last_seen            # Recency boost
                + w3 * spaced_rep_urgency              # Review due boost
                + w4 * novelty_boost                   # Never-seen boost
                - w5 * times_seen_this_week            # Fatigue penalty
```

Default weights: `w1=0.35, w2=0.25, w3=0.25, w4=0.10, w5=0.05`

- `spaced_rep_urgency`: 1.0 if `today >= next_review`, 0.0 otherwise. Linearly ramps from 0 to 1 in the 2 days before the review date.
- `novelty_boost`: 1.0 if `times_seen == 0`, else 0.0.
- Topics are ranked by priority. The top N (from `items_per_session` in config) are selected.
- Item types are assigned round-robin from SESSION_SHAPE, then shuffled.

### 7.3 Difficulty Adjustment (global per track)

A single float (1.0–5.0) that tracks the overall challenge level.

```
After each session:
  avg_score = mean of all item scores in the session
  if avg_score >= 4.0:  difficulty += 0.2
  if avg_score <= 2.0:  difficulty -= 0.3  (drop faster than rise)
  else:                 difficulty += (avg_score - 3.0) * 0.1
  difficulty = clamp(difficulty, 1.0, 5.0)
```

This difficulty value is passed to the LLM as part of the session prompt. The subject file's DIFFICULTY_LEVELS descriptions tell the LLM what each level means.

### 7.4 Session Composition

The scoring engine determines the teach/practice/review ratio:

| Condition | Teach | Practice | Review |
|---|---|---|---|
| Most selected topics are new or weak (competence < 2.0) | 40% | 40% | 20% |
| Mixed competence levels | 20% | 50% | 30% |
| Most selected topics are strong (competence > 3.5) | 0% | 30% | 70% |

"Teach" means the LLM generates a teaching block (using TEACHING_STYLE) before the practice item.
"Review" means the item is a spaced-repetition callback — a quick recall check on a previously mastered topic.

### 7.5 Remediation

When a topic's score drops below 2 in any session:

1. That topic's state transitions to `needs_remediation`.
2. In the next session, that topic gets a teaching block (explanation + worked example) followed by a practice item at one difficulty level lower than the previous attempt.
3. If the score improves to 3+, remediation ends. If not, it persists.
4. Remediated topics get a priority boost of +0.5 to ensure they appear in the next session.

### 7.6 Spaced Repetition

Simple interval-based scheduling:

```
After scoring a topic:
  if score >= 4 (passed):
    review_interval *= 2.0   (double the gap)
    next_review = today + review_interval days
  elif score >= 3 (okay):
    review_interval *= 1.0   (same interval)
    next_review = today + review_interval days
  else (failed):
    review_interval = 1.0    (reset to tomorrow)
    next_review = tomorrow
```

- Initial interval: 1.0 day (see the topic again tomorrow).
- Max interval: 30 days (cap to prevent topics from disappearing entirely).
- This is the Leitner system simplified. Comment in code: "Upgrade path: SM-2 (supermemo) or FSRS (open spaced repetition) for evidence-based scheduling."

---

## 8. LLM Interaction Design

### 8.1 Provider Adapter

```python
# src/provider.py — the ONLY file that touches LiteLLM.

import litellm

def complete(
    system_prompt: str,
    user_prompt: str,
    model: str,
    temperature: float = 0.7,
    max_tokens: int = 4000,
    response_format: dict | None = None,   # For JSON mode where supported
) -> str:
    """Single entry point for all LLM calls. Returns the text response."""
    response = litellm.completion(
        model=model,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        temperature=temperature,
        max_tokens=max_tokens,
        response_format=response_format,
    )
    return response.choices[0].message.content
```

No other file imports litellm. No other file imports any vendor SDK. Switching providers = changing the model string in config + setting the right env var.

### 8.2 Session Generation Prompt

The session prompt is constructed by `src/session.py` and has three parts:

**System prompt** (from the subject file):
```
You are a learning session generator for: {SUBJECT}
Learner context: {LEARNER_CONTEXT}
Teaching style: {TEACHING_STYLE}
Grading rubric: {GRADING_RUBRIC}
```

**User prompt** (constructed by the scoring engine):
```
Generate a learning session with the following specifications.

Overall difficulty level: {difficulty}/5

Items to generate:
1. Topic: "attention_mechanisms" | Type: conceptual | Difficulty: 3/5 | Mode: TEACH_THEN_PRACTICE
   (Learner competence: 1.8/5 — needs remediation. Teach the concept first, then test.)
2. Topic: "loss_functions" | Type: applied | Difficulty: 3/5 | Mode: PRACTICE
   (Learner competence: 3.2/5 — progressing. Direct practice.)
3. Topic: "transformers" | Type: coding | Difficulty: 2/5 | Mode: TEACH_THEN_PRACTICE
   (Learner competence: 0.0/5 — never seen. Introduce with teaching block.)
4. Topic: "batch_normalization" | Type: debugging | Difficulty: 4/5 | Mode: REVIEW
   (Learner competence: 4.1/5 — spaced review. Quick recall check.)
5. Topic: "optimizers" | Type: system_design | Difficulty: 3/5 | Mode: PRACTICE
   (Learner competence: 2.9/5 — mid-range. Standard practice.)

Respond in the following JSON format only:
{session_json_schema}
```

**The LLM never decides which topics to cover.** The scoring engine decides. The LLM generates pedagogically sound content within those constraints.

### 8.3 Expected JSON Output Schema

```json
{
  "session": {
    "date": "2026-07-11",
    "items": [
      {
        "topic": "attention_mechanisms",
        "item_type": "conceptual",
        "difficulty": 3,
        "mode": "teach_then_practice",
        "teaching_block": "Attention lets a model focus on relevant parts of the input rather than treating all positions equally. Think of it as a soft lookup: the Query asks 'what am I looking for?', Keys say 'here is what I contain', Values provide the actual content. The score between Q and K determines how much of each V to use. The scaling factor 1/sqrt(d_k) prevents dot products from growing so large that softmax saturates. Common trap: attention is O(n^2) in sequence length — interviewers love asking when this matters.",
        "question": "A colleague understands single-head attention. Explain what multi-head attention adds and why it helps. Give a concrete example of what different heads might learn.",
        "expected_answer": "Multi-head attention runs several attention operations in parallel with separate learned projections..."
      },
      {
        "topic": "batch_normalization",
        "item_type": "debugging",
        "difficulty": 4,
        "mode": "review",
        "teaching_block": null,
        "question": "Quick recall: your model's validation accuracy is much worse than training accuracy, but only after you switched from batch size 256 to 8. BatchNorm is in the architecture. What's happening?",
        "expected_answer": "With batch size 8, batch statistics become noisy estimates..."
      }
    ]
  }
}
```

### 8.4 LLM-as-Judge (Optional)

When `enable_llm_judge: true` in config, after the user enters a free-text answer, a second LLM call evaluates it:

```
System: You are an expert evaluator for {SUBJECT}.
User: 
  Question: {question}
  Expected answer: {expected_answer}
  Rubric: {GRADING_RUBRIC}
  Student answer: {user_answer}
  
  Score the answer 1-5 per the rubric. Respond in JSON:
  {"score": <int>, "feedback": "<2-3 sentences on what was good and what was missed>"}
```

This score is stored alongside the self-score. If both exist, the scoring engine uses the average, weighted 40% self / 60% LLM-judge.

---

## 9. CLI Design

Built with Typer. Color output via Rich.

### Commands

```
orbit init                    Set up config, create directories, verify API key
orbit learn                   Run today's interactive session for the active track
orbit learn --track spanish   Run a specific track
orbit status                  Show per-topic competence, streaks, upcoming reviews
orbit status --track all      Dashboard across all tracks
orbit history                 Show recent session scores
orbit calibrate               Run initial calibration for a new track
orbit export --format csv     Export all learning data
orbit export --format json    Export as JSON
orbit summary                 Weekly progress summary
```

### Interactive Session Flow (`orbit learn`)

```
┌──────────────────────────────────────────────────────┐
│  Orbit — ML Interview Prep                           │
│  Session #14  |  Day 14  |  Difficulty: 3.2/5  |  🔥 7-day streak  │
└──────────────────────────────────────────────────────┘

── 1/5  Topic: Attention Mechanisms  |  ★★★☆☆  |  Conceptual ──

📖 TEACH:
Attention lets a model focus on relevant parts of the input
rather than treating all positions equally. Think of it as a 
soft lookup: Query asks "what am I looking for?", Keys say 
"here is what I contain", Values provide the content. The 
scaling factor 1/√d_k prevents softmax saturation.

📝 QUESTION:
A colleague understands single-head attention. Explain what 
multi-head attention adds and why it helps. Give a concrete 
example of what different heads might learn.

Your answer (or press Enter to skip): ▌

── Expected Answer ──
Multi-head attention runs several attention operations in
parallel with separate learned projections. This lets the 
model attend to different relationship types simultaneously
— one head might track syntax, another semantics, another
positional proximity...

How did you do?
  [1] Blank    [2] Partial    [3] Got the idea    [4] Solid    [5] Nailed it
> 3

✓ Recorded. Moving to next item...
```

---

## 10. Delivery Methods

All methods implement the same interface:

```python
class Delivery(Protocol):
    def send(self, session: Session, track_name: str) -> None: ...
```

| Method | How it works | Tradeoffs |
|---|---|---|
| `terminal` | Interactive CLI session (default) | Best learning UX; requires active user |
| `markdown` | Saves session to `output/<track>/<date>.md` | Good for cron; passive reading only |
| `email` | Sends via SMTP (or Resend/SendGrid) | Push notification; not interactive |

For scheduled runs (cron/GitHub Actions), the system generates the session and delivers via the configured method. The user scores later via `orbit score --session <id>`.

---

## 11. File & Directory Structure

```
orbit/
├── config.yaml                    # User configuration
├── subjects/                      # Subject prompt files (the swappable units)
│   ├── ml_interview.md
│   ├── spanish_b2.md
│   ├── python_fundamentals.md
│   ├── system_design.md
│   └── sql_mastery.md
├── src/
│   ├── __init__.py
│   ├── cli.py                     # Typer CLI commands
│   ├── config.py                  # Config loading and validation
│   ├── provider.py                # LiteLLM adapter (ONLY LLM interface)
│   ├── subject.py                 # Subject file parser
│   ├── session.py                 # Session generation (prompt building + LLM call)
│   ├── scoring.py                 # Competence, difficulty, topic prioritization
│   ├── scheduler.py               # Spaced repetition intervals
│   ├── persistence.py             # SQLite operations
│   ├── delivery.py                # Terminal / markdown / email output
│   ├── dashboard.py               # Rich-based progress visualization
│   ├── judge.py                   # LLM-as-judge evaluation
│   └── models.py                  # Pydantic data models (Session, Item, TopicStats)
├── data/                          # SQLite databases (one per track, gitignored)
│   └── .gitkeep
├── output/                        # Generated session files (gitignored)
│   └── .gitkeep
├── tests/
│   ├── test_scoring.py
│   ├── test_scheduler.py
│   ├── test_session.py
│   ├── test_config.py
│   └── test_subject.py
├── notebooks/
│   └── learning_analytics.ipynb   # Visualization of learning data
├── .github/
│   └── workflows/
│       └── daily_session.yml      # GitHub Actions scheduled workflow
├── .env.example                   # Template for env vars (never commit .env)
├── .gitignore
├── README.md
├── CONTRIBUTING.md
├── LICENSE                        # MIT
├── pyproject.toml                 # Project metadata + dependencies
└── DESIGN_DOC.md                  # This file
```

---

## 12. Dependencies

Minimal by design:

```toml
[project]
dependencies = [
    "litellm>=1.40",       # Provider-agnostic LLM calls
    "typer>=0.12",         # CLI framework
    "rich>=13.0",          # Terminal formatting and dashboards
    "pydantic>=2.0",       # Data validation and models
    "pyyaml>=6.0",         # Config parsing
]

[project.optional-dependencies]
email = ["resend>=2.0"]    # Only needed for email delivery
dev = [
    "pytest>=8.0",
    "pytest-cov>=5.0",
    "ruff>=0.5",           # Linting
]
```

No LangChain. No vector databases. No web frameworks. Six core dependencies.

---

## 13. Execution Plan — Phased Development

Each phase produces working, runnable code. Claude Code should implement one phase, provide run instructions, then stop and wait.

---

### Phase 0 — Skeleton + Provider Abstraction + Hello World

**Goal:** Prove the plumbing. A script reads config, calls an LLM, and prints the response. Switching models = editing one config line.

**Build:**
1. Create the repo structure (directories, `pyproject.toml`, `.gitignore`, `.env.example`).
2. Write `config.yaml` with model string and placeholder track config.
3. Implement `src/config.py` — load and validate config with Pydantic.
4. Implement `src/provider.py` — the LiteLLM adapter (single `complete()` function).
5. Write a `main.py` entry point that loads config, calls the provider with a hardcoded test prompt ("What is spaced repetition? Answer in 2 sentences."), and prints the response.
6. Write initial `README.md` with setup and run instructions.

**Done when:** `python main.py` prints a model response. Changing the model string in `config.yaml` and the env var switches providers with zero code changes.

**Key design decision:** LiteLLM over raw SDK calls. Tradeoff: adds a dependency but eliminates per-provider adapter code. One model string format (`provider/model-name`) handles everything.

---

### Phase 1 — Subject Files + Session Generation

**Goal:** Load a subject prompt file, generate a structured learning session, display it in the terminal. Swapping the subject file changes the domain with no code change.

**Build:**
1. Create `subjects/ml_interview.md` and `subjects/spanish_b2.md` with the full format (SUBJECT, LEARNER_CONTEXT, SESSION_SHAPE, TOPICS, DIFFICULTY_LEVELS, TEACHING_STYLE, GRADING_RUBRIC).
2. Implement `src/subject.py` — parse the subject file into a Pydantic model. Validate all required fields.
3. Implement `src/models.py` — define `Session`, `Item`, `SubjectConfig` as Pydantic models.
4. Implement `src/session.py` — construct the system + user prompt from the subject file, call the provider, parse the JSON response into Session/Item models. Include retry logic (up to 2 retries) if the LLM returns malformed JSON.
5. Implement basic terminal display — print the session formatted with Rich (topic headers, question text, expected answers).
6. Optionally save the session as a markdown file in `output/`.

**Done when:** `python main.py` generates a well-formatted session for the active track. Changing `active_track` in config and pointing to a different subject file changes the subject with zero code changes.

**Key design decision:** Structured JSON output from the LLM, validated by Pydantic. Tradeoff: requires a detailed JSON schema in the prompt (verbose), but guarantees the output is machine-parseable. The alternative (freeform markdown) is fragile to parse.

---

### Phase 2 — Persistence + Interactive Sessions + Metrics

**Goal:** Sessions are interactive (present one item at a time, collect scores). All data persists across runs. Per-topic performance is queryable.

**Build:**
1. Implement `src/persistence.py` — SQLite setup, create tables (sessions, items, topic_stats), read/write functions. Use context managers for connections.
2. Implement `src/cli.py` — set up Typer with `orbit learn` and `orbit status` commands.
3. Make `orbit learn` interactive: present one item at a time, wait for user to type answer (optional) and self-score (1-5), store results immediately.
4. Implement `orbit status` — query topic_stats and display per-topic competence, times seen, last seen, and current streak using a Rich table.
5. Implement `orbit history` — show recent sessions with average scores.
6. Update `README.md` with new commands.

**Done when:** History survives across runs. `orbit status` shows per-topic performance data that grows with each session. Running `orbit learn` multiple times builds up a visible history.

**Key design decision:** SQLite over JSON files. Tradeoff: slightly more setup code, but enables SQL queries for analytics, handles concurrent access safely, and scales to thousands of sessions without loading everything into memory.

---

### Phase 3 — Adaptive Engine

**Goal:** The system reacts to performance. Weak topics get more attention. Difficulty tracks the learner. Remediation teaches before re-testing. Spaced repetition schedules reviews.

**Build:**
1. Implement `src/scoring.py`:
   - EWMA competence calculation (update after each scored item).
   - Topic priority function (weakness + recency + spaced rep urgency + novelty - fatigue).
   - Session composition logic (determine teach/practice/review ratio).
   - Difficulty adjustment (post-session update).
   - Remediation detection (score < 2 triggers remediation flag).
2. Implement `src/scheduler.py`:
   - Interval calculation (pass: double interval, fail: reset to 1 day).
   - `next_review` date computation.
   - Review urgency scoring.
3. Modify `src/session.py`:
   - Use scoring engine output to build the session prompt (topic list with competences, modes, difficulties).
   - Include teaching blocks for remediation and new topics.
   - Mark review items distinctly.
4. Implement initial calibration (`orbit calibrate`):
   - Generate 5 items at varying difficulty across key topics.
   - User attempts them, scores are used to set initial competence and difficulty.
5. Write `tests/test_scoring.py` and `tests/test_scheduler.py` — unit tests for the scoring functions and spaced repetition logic. These are deterministic and testable without LLM calls.

**Done when:** Over 5+ simulated sessions, observable behavior shows: weak topics appear more frequently, difficulty increases when scoring well, failed topics get teaching blocks before re-testing, and mastered topics reappear on a spaced schedule.

**Key design decision:** Rule-based scoring over ML-based. Tradeoff: less sophisticated than a neural scheduler, but transparent, testable, and explainable. The weights in the priority function are tunable. Comment in code points to SM-2/FSRS as principled upgrades.

---

### Phase 4 — Scheduling + Delivery

**Goal:** Sessions generate and deliver on a schedule without manual triggering.

**Build:**
1. Implement `src/delivery.py`:
   - `TerminalDelivery` — the existing interactive flow (default).
   - `MarkdownDelivery` — save session as `output/<track>/<date>.md`.
   - `EmailDelivery` — send via SMTP or Resend API. Subject line includes track name and streak count.
2. Add `orbit score --session <id>` command — for scoring sessions delivered via non-interactive methods (email, markdown). Presents items one at a time for scoring.
3. Write a cron-compatible entry point: `orbit run --deliver` that generates + delivers without interactive input.
4. Create `.github/workflows/daily_session.yml`:
   - Scheduled trigger (cron syntax for desired time).
   - Checks out repo, installs deps, runs `orbit run --deliver`.
   - Commits updated SQLite DB back to repo (state persistence).
   - Secrets: API key stored as GitHub repo secret.
5. Document tradeoffs in README:
   - Cron: simplest, but machine must be on.
   - GitHub Actions: reliable, but state lives in repo and secrets need setup.
   - Future: serverless (AWS Lambda, Modal) for zero-maintenance.

**Done when:** A session is generated and delivered on a schedule (either cron or GitHub Actions) without the user triggering it manually.

**Key design decision:** Pluggable delivery over single method. Tradeoff: slightly more code upfront, but new delivery methods (Slack, Telegram, GitHub Issues) are a single class implementation away.

---

### Phase 5 — Multi-Track + Community Subjects + Polish

**Goal:** Multiple independent learning tracks. Bundled subject files. A polished, ready-to-share experience.

**Build:**
1. Update CLI to support `--track` flag on all commands. `orbit learn --track spanish` runs a specific track.
2. Ensure each track has isolated state (its own SQLite DB, its own difficulty level, its own topic stats).
3. Add `orbit summary` — weekly digest across all tracks (total sessions, strongest/weakest topics, streaks, difficulty progression).
4. Create 3-5 bundled subject files:
   - `ml_interview.md` — ML/DL interview prep
   - `system_design.md` — System design interview prep
   - `python_fundamentals.md` — Python deep knowledge
   - `sql_mastery.md` — SQL from intermediate to advanced
   - `spanish_b2.md` — Spanish conversational fluency
5. Implement `src/dashboard.py` — Rich-based terminal dashboard showing:
   - Per-topic competence bars
   - Difficulty progression over time (sparkline)
   - Streak counter
   - Upcoming reviews
   - Session count and overall progress
6. Add `orbit export --format csv` and `orbit export --format json`.
7. Create `CONTRIBUTING.md` — how to write and submit new subject files.
8. Polish `README.md`:
   - Animated GIF/screenshot of an interactive session at the top.
   - Three-line quickstart.
   - "How it works" section with the adaptation loop diagram.
   - List of available subjects.
   - Architecture section for contributors.
9. Add `LICENSE` (MIT).
10. Set up `pyproject.toml` for PyPI publishing (`pip install orbit-learn`).

**Done when:** Multiple tracks run independently. The repo looks professional, is well-documented, and a new user can go from `pip install orbit-learn` to their first session in under two minutes.

---

### Phase 6 (Post-Launch) — Advanced Features

Not part of the initial build. These are documented here for future extension:

- **Pluggable scoring strategies:** SM-2 and FSRS as selectable options in config.
- **Learning analytics notebook:** Jupyter notebook with matplotlib/plotly visualizations of forgetting curves, topic mastery trajectories, and difficulty progression using real exported data.
- **Hermes Agent integration:** An optional Hermes skill that wraps Orbit for always-on delivery via Telegram/Discord.
- **GitHub Issues delivery:** Each session becomes a GitHub Issue; user scores by commenting.
- **Voice mode:** Speech-to-text answers for language learning tracks.
- **Collaborative subjects:** A central registry where users can publish and discover subject files.
- **Web dashboard:** A simple local web UI (FastAPI + HTMX) as an alternative to the terminal dashboard.

---

## 14. Testing Strategy

- **Scoring and scheduling logic:** Fully unit-tested. These are pure functions — deterministic input/output, no LLM calls needed. This is where most tests live.
- **Config and subject parsing:** Validated via Pydantic. Test with valid and invalid files to ensure clear error messages.
- **Session generation:** Integration tests with mocked LLM responses (save real LLM outputs as fixtures, test the parsing/validation pipeline against them).
- **End-to-end:** A script that simulates 10 sessions with predetermined scores and verifies that topic prioritization, difficulty adjustment, and spaced repetition behave as expected.

---

## 15. Instructions for Claude Code

When building this project:

1. Read this design doc fully before starting any phase.
2. Build ONE phase at a time. At the end of each phase, provide exact run instructions and stop.
3. Keep code simple and readable. Prefer clarity over cleverness.
4. Every file should have a module-level docstring explaining its responsibility in one sentence.
5. Use type hints throughout. Use Pydantic for all data models.
6. The provider adapter (`src/provider.py`) is the ONLY file that imports litellm. Enforce this.
7. All secrets come from environment variables. Never hardcode API keys.
8. Write the scoring engine tests (Phase 3) BEFORE implementing the scoring engine. The tests define the expected behavior.
9. Use Rich for all terminal output. The CLI should feel polished from Phase 2 onward.
10. After each phase, update README.md with the new commands and capabilities.

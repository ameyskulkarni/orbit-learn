# Contributing to Orbit

Thanks for wanting to contribute! Orbit's whole thesis is that a subject file is the product — so the highest-leverage way to help is to **write a great subject file** for a domain you know well. Bug fixes and small features are welcome too.

---

## Contributing a new subject

Every subject is a single markdown file at `subjects/<name>.md`. Same engine, any domain.

### 1. Copy an existing one

```bash
cp subjects/ml_interview.md subjects/your_topic.md
```

### 2. Fill in the seven required fields

| Field | What it is |
|---|---|
| `SUBJECT` | One-line title of what you're teaching. |
| `LEARNER_CONTEXT` | Who is the learner? What do they know, what do they want to learn? |
| `SESSION_SHAPE` | Item types + how many of each per session. |
| `TOPICS` | Flat list of `snake_case` topic names. These are what the scoring engine tracks. |
| `DIFFICULTY_LEVELS` | Descriptions of what an item at each of levels 1-5 tests. |
| `TEACHING_STYLE` | Instructions the LLM follows when generating a teaching block. |
| `GRADING_RUBRIC` | 1-5 scale shown to the learner for self-scoring (and to the LLM if judge mode is on). |

### 3. Register the track in `config.yaml`

```yaml
tracks:
  your_topic:
    subject_file: "subjects/your_topic.md"
    items_per_session: 5
    scoring_strategy: "ewma"
    enable_llm_judge: false
```

### 4. Sanity-check it

```bash
orbit init                            # confirms your subject file parses
orbit learn --track your_topic        # try a session
```

### 5. Open a PR

Include:
- A one-sentence description of who this subject is for.
- Sample output from `orbit learn --track your_topic` (paste a few items into the PR body).
- Any notes on the difficulty scale or teaching style you tuned.

---

## Subject-file gotchas

The parser is YAML-with-markdown. A few sharp edges worth knowing:

- **Avoid inline colons in `LEARNER_CONTEXT` if it wraps to multiple lines.** YAML reads `like this:` inside a folded scalar as a nested mapping and errors out. Use an em-dash or restructure.
- **Keep `DIFFICULTY_LEVELS` values on a single line.** Multi-line wrapped values sometimes trip YAML depending on the punctuation.
- **`SESSION_SHAPE` entries are single-key dicts** so each can have a trailing `# comment`. See any bundled subject file.
- **`TEACHING_STYLE` and `GRADING_RUBRIC` are literal block scalars** (`|`). Preserve the indentation exactly.

---

## Contributing code

### Dev setup

```bash
git clone https://github.com/orbit-learn/orbit-learn
cd orbit-learn
poetry install                        # includes dev deps (pytest, pytest-cov, ruff)
```

### Run the tests

```bash
poetry run pytest                     # 37 tests, all pure functions, sub-second
poetry run pytest --cov=orbit_learn   # with coverage
```

### Style

- **Ruff** for lint (`poetry run ruff check .` and `poetry run ruff format .`).
- Type hints everywhere. Pydantic for data models.
- **One rule that must not break**: `orbit_learn/provider.py` is the ONLY module that may import `litellm`. Everything else routes LLM calls through `provider.complete()`. If you want a new provider, add it to LiteLLM upstream — don't fork the adapter.

### Adding a delivery method

Implement the `Delivery` protocol in `orbit_learn/delivery.py`:

```python
class SlackDelivery:
    def __init__(self, webhook_url: str) -> None:
        self.webhook_url = webhook_url

    def send(self, session, subject, track_name, streak=0) -> str | None:
        # POST to self.webhook_url
        return f"slack:{self.webhook_url}"
```

Wire it into `get_delivery()` and add config schema in `config.py`. That's it.

### Adding a scheduling strategy

Orbit ships three: `ewma` (Leitner default), `sm2`, and `fsrs`. All three implement the `SchedulingStrategy` protocol in [`orbit_learn/strategies.py`](orbit_learn/strategies.py) — see design doc §16 for the full spec.

To add a fourth (e.g., a personalized FSRS-5, a custom SM-15 variant, or the reference `fsrs` PyPI package):

1. **Write tests first** in `tests/test_your_strategy.py`. The Phase-3 rule applies to Phase 6 too — deterministic scheduling code is unit-testable and should be tested before it's written.

2. **Implement the protocol** in `orbit_learn/strategies.py`:

   ```python
   class YourStrategy:
       name: ClassVar[str] = "your_name"

       def initial_state(self) -> dict:
           """JSON-serializable per-topic state before the first review."""

       def update(self, state: dict, score: int, review_date: date) -> dict:
           """Return NEW state after the given 1-5 Orbit score."""

       def interval_days(self, state: dict) -> float:
           """Days until the topic should next appear."""
   ```

3. **Register in the factory** — add your class to the `_STRATEGIES` dict in the same file.

4. **Add to the `Literal` type** in `TrackConfig.scoring_strategy` (see [`orbit_learn/config.py`](orbit_learn/config.py)) so config validation accepts it.

That's it. No changes to `persistence.py`, `cli.py`, or the priority function — competence stays EWMA across all strategies (design doc §16.2), so the rest of Orbit doesn't care which scheduler you plug in.

**Grade mapping.** Orbit uses a 1-5 self-score. If your strategy natively uses a different scale (SM-2's 0-5, FSRS's Again/Hard/Good/Easy), map inside `update()`. See `orbit_score_to_fsrs_rating` in strategies.py for an example.

**Recomputing after switching.** `refresh_topic_stats` replays every score for a topic through the current strategy, so switching a track's `scoring_strategy` in `config.yaml` is safe — next `orbit learn` scores an item, `topic_stats` recomputes under the new strategy from full history.

---

## Filing bugs

Please include:

- Which command you ran and the full stderr.
- Your `config.yaml` (with API keys redacted).
- Provider + model string.
- Rough repro steps.

---

## Code of conduct

Be kind. Explain your reasoning. Assume good faith. That's it.

---

## License

By contributing you agree that your contributions will be licensed under the MIT License.

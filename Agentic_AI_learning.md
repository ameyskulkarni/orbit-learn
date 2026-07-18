# Build Prompt — Adaptive Daily Learning Framework

*Hand this whole file to Claude (ideally Claude Code, so it can write files directly). If you're in Claude Code, save this as `BUILD_PROMPT.md` in an empty repo and say: "Follow BUILD_PROMPT.md. Start with Phase 0, then stop and wait for me."*

---

## Context and goal

I want to build, with your help and **while learning how it works**, a small, open-source, provider-agnostic "daily adaptive learning" framework in Python.

The idea: a user writes a short prompt/config describing something they want to learn (e.g. "Spanish B2 conversation," "machine learning interview prep," "music theory"). Every day the system generates a tailored practice session, tracks how the user does, and **adapts** — leveling questions up as they improve, teaching more and re-testing topics they get wrong, and revisiting weak topics after a few days (spaced repetition).

It must be **generic**: nothing in the core engine is specific to any one subject. A subject is just a swappable prompt file. I should be able to keep several prompt files (one per learning track) and pick which to run. Later I'll drop in an "interview prep" prompt file and it should just work, no code changes.

## How I want you to work with me (important — read first)

- Build this **one phase at a time.** At the end of each phase, give me something I can actually run, tell me exactly how to run it, then **stop and wait** for me to test and confirm before starting the next phase. Do not run ahead.
- **Teach as you go.** I'm doing this partly to learn. For each phase, briefly explain the design choices and the *why*, and name the main tradeoff you weighed. Keep explanations short and concrete.
- **Keep it simple and minimal.** Prefer the simplest thing that works over the clever thing. Minimal dependencies. No framework I don't need. When there's a simple path and a sophisticated path, take the simple one now and leave a one-line note about the future upgrade.
- **No premature building.** Don't implement future phases early or over-abstract beyond what's needed to keep subjects swappable.
- Ask me a question **only** if a decision genuinely blocks you. Otherwise pick a sensible default, state it in one line, and proceed.

## Architectural guardrails (apply from Phase 0)

- **Language:** Python. **Secrets:** environment variables only, never in code or committed files.
- **Provider-agnostic from day one.** Every model call goes through ONE thin adapter so I can use any provider (Anthropic, OpenAI, Gemini, a local model, etc.) by changing config only. Use **LiteLLM** (or an OpenAI-compatible layer such as **OpenRouter**) so that a single model string plus the matching API-key env var switches providers with zero logic changes. No other file may import a vendor SDK directly.
- **Config- and prompt-driven.** A `config.yaml` holds: provider/model, the active subject prompt-file path, the delivery method, and the schedule. A subject = a prompt file (+ a little metadata). Swapping subjects = swapping the prompt file.
- **State is local and simple.** Start with SQLite (or plain JSON if that's simpler at first). No external database, no cloud services in early phases.

## Phases

**Phase 0 — Skeleton + provider abstraction + hello world.**
Prove the plumbing. Create the repo layout, `config.yaml`, the provider adapter, and a script that reads config, calls the model with a trivial hardcoded prompt, and prints the reply. Run manually.
*Done when:* I run it, get a model response, and can switch models by editing one line of config.

**Phase 1 — Prompt-file-driven daily session.**
Real sessions, still run manually, printed to terminal (and optionally saved as a markdown file). A subject prompt file defines what to teach and how a session is structured; the model generates today's session from it.
*Done when:* I point config at a prompt file and get a well-formatted session, and swapping the prompt file changes the subject with no code change.

**Phase 2 — Persistence + metrics.**
Remember what happened. After a session, record results — start with simple self-scoring per item (1–5) plus the topic each item belongs to. Persist sessions, items, topics, scores, and dates.
*Done when:* history survives across runs and I can see per-topic performance over time.

**Phase 3 — Adaptivity (the heart of it).**
Make the system react to my performance. Implement:
(a) a per-topic rolling competence score derived from my results;
(b) session generation that **weights toward my weak and not-recently-seen topics**;
(c) a **difficulty knob** that rises when I score well and drops when I struggle;
(d) **remediation** — when I get a topic wrong, the next session teaches it more (explanation + worked examples) before re-testing it;
(e) **spaced re-testing** — revisit a topic after a few days to confirm retention; if I pass, space it out further; if not, bring it back sooner.
Keep the algorithm simple and readable — a lightweight rule-based scheme is fine. Note in a comment that SM-2 / FSRS are the principled upgrades for later.
*Done when:* over several simulated days, weak topics visibly get more attention and difficulty tracks my performance.

**Phase 4 — Scheduling / unattended delivery.**
Make it run on its own, simplest reliable option first. Order: (1) runnable manually, (2) a local **cron** job, (3) a **GitHub Actions** scheduled workflow for when my machine is off. For delivery, go simplest-first too: print → save file → email. Tell me the tradeoffs in a sentence (local cron is simplest but needs my machine awake; GitHub Actions is reliable but needs secrets stored in the repo and state committed back).
*Done when:* a session is generated and delivered on a schedule without me triggering it.

**Phase 5 — Multiple tracks + repurpose for interview prep.**
Support multiple prompt files (one per learning track), each with its own state, plus a way to choose which track(s) run. Then create one prompt file for ML/AI interview prep to prove the swap works end-to-end. Add a simple weekly summary report per track.
*Done when:* I can maintain several tracks, run any of them, and the interview-prep track works purely by dropping in a prompt file.

## Deliverables each phase

Working code in a clear, open-source-friendly repo layout; a short README section for the phase; exact run instructions; and a 3–5 line explanation of the key design decisions and the tradeoff you chose. Maintain a growing top-level `README.md`.

## Start now

Begin with Phase 0: first propose the repo layout and the `config.yaml` schema (show them to me), then implement Phase 0, then **stop and wait** for me to test.

---

## Appendix — what a "subject prompt file" looks like (for your reference)

This is the swappable unit. Keep its format consistent so any subject works. Example for one track:

```
# subjects/spanish_b2.md
SUBJECT: Spanish, targeting B2 conversational fluency
LEARNER_CONTEXT: Adult, intermediate, can read but freezes when speaking.
SESSION_SHAPE: 5 items/day — mix of vocab-in-context, a short translation,
  one grammar drill, one listening/reading comprehension, one free-response prompt.
TOPICS: [subjunctive, ser vs estar, past tenses, connectors, idioms, ...]
TONE: encouraging, concise, corrections explained simply.
GRADING_RUBRIC: for each item describe what a weak / okay / strong answer looks like.
```

Later, the interview-prep track is just another file (e.g. `subjects/ml_interview.md`) with its own SUBJECT, SESSION_SHAPE (the 7-slot ML/DL/CV/system-design/research/debugging/behavioral set), TOPICS, and rubric. Same engine, different file.

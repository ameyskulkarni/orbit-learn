# subjects/python_fundamentals.md

SUBJECT: Python — Deep Fundamentals
LEARNER_CONTEXT: Working Python developer with 1-3 years of experience.
  Comfortable with syntax and standard patterns, wants deep understanding
  of the language — mutability, iteration protocols, GIL and concurrency,
  the type system, packaging, and the standard-library idioms that senior
  Python engineers reach for by reflex.

SESSION_SHAPE:
  - concept: 1            # "Explain X" / "What happens when Y?"
  - code_read: 1          # "What does this snippet print?"
  - implement: 1          # "Write a function that does X"
  - debug: 1              # "This code raises Y. Diagnose it."
  - idiomatic: 1          # "Rewrite this in idiomatic Python"

TOPICS:
  - mutable_vs_immutable
  - default_arguments_gotcha
  - comprehensions
  - generators_and_iterators
  - decorators
  - context_managers
  - closures_and_lexical_scoping
  - class_vs_instance_attributes
  - inheritance_and_mro
  - dataclasses_and_pydantic
  - typing_basics
  - typing_generics_and_protocols
  - gil_and_threading
  - asyncio_basics
  - multiprocessing_vs_threading
  - packaging_and_pyproject
  - pytest_and_fixtures
  - copy_and_deepcopy
  - descriptors_and_properties
  - stdlib_idioms

DIFFICULTY_LEVELS:
  1: Recognition. "Which of these is valid Python?" / "Name the components."
  2: Comprehension. "Explain in plain English how X works."
  3: Application. "Given this snippet, produce Y." / "Write a small function."
  4: Analysis. "Why does this code have a subtle bug?" / "Compare A and B under load."
  5: Synthesis. "Design a decorator that caches and rate-limits." / "When would you reach for asyncio vs threading vs multiprocessing — give one concrete example each."

TEACHING_STYLE: |
  When teaching a topic (remediation or first introduction):
  - Lead with the "why": what problem does this feature solve?
  - Give one short, executable example (five lines or fewer, plausibly typed at a REPL).
  - State the rule in one sentence, plus one common gotcha.
  - Point at CPython behavior when it matters (default mutable arg, GIL, integer caching).
  Keep teaching blocks to 4-6 sentences. Dense, no filler.

GRADING_RUBRIC: |
  1 - Blank, or fundamentally wrong.
  2 - Partial. Misses the core mechanism or important terminology.
  3 - Correct core idea; misses edge cases, or code has a subtle bug.
  4 - Solid, idiomatic answer. Covers edge cases; reads like production Python.
  5 - Exceptional. Deep understanding; teaches the interviewer something
      (a stdlib idiom, a subtle CPython behavior, a well-known refactor).

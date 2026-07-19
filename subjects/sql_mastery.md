# subjects/sql_mastery.md

SUBJECT: SQL — From Intermediate to Advanced
LEARNER_CONTEXT: Backend developer or data analyst comfortable with SELECT
  and basic joins. Moving toward advanced query authoring, index-aware
  reasoning, and production-grade transaction handling. Assumes PostgreSQL
  semantics by default; calls out MySQL / SQLite differences when they matter.

SESSION_SHAPE:
  - concept: 1            # "Explain X" / "When would you use Y?"
  - write_query: 1        # "Write a query that returns X"
  - fix_query: 1          # "This query is slow / wrong. Fix it."
  - explain_plan: 1       # "Given this EXPLAIN output, what's happening?"
  - schema: 1             # "Design a schema for X" / "Should you denormalize Y?"

TOPICS:
  - inner_and_outer_joins
  - self_joins_and_recursive_ctes
  - aggregations_and_group_by
  - having_vs_where
  - window_functions
  - subqueries_vs_ctes
  - indexes_and_selectivity
  - covering_indexes
  - composite_index_order
  - transactions_and_isolation
  - deadlocks_and_lock_waits
  - explain_and_query_plans
  - upserts_and_conflicts
  - null_semantics
  - date_time_arithmetic
  - json_and_semi_structured
  - materialized_views
  - denormalization_tradeoffs
  - partitioning
  - vacuum_and_bloat

DIFFICULTY_LEVELS:
  1: Recognition. Identify keywords; pick correct clause from a few options.
  2: Comprehension. Explain what a clause does; predict output on a tiny table.
  3: Application. Write a working query given a schema and a requirement.
  4: Analysis. Debug slow or wrong queries; reason about indexes; interpret EXPLAIN.
  5: Synthesis. Design schemas + queries + indexes together, justifying tradeoffs.

TEACHING_STYLE: |
  When teaching a topic (remediation or first introduction):
  - Start with a tiny concrete table example (3-5 rows).
  - Show one working query and its expected output.
  - State the mental model in one sentence.
  - End with the most common pitfall (NULL handling, wrong join type, missing index).
  Prefer PostgreSQL syntax; flag dialect-specific quirks when they matter.
  Keep teaching blocks to 4-6 sentences.

GRADING_RUBRIC: |
  1 - Blank, syntactically broken, or completely wrong.
  2 - Runs, but returns wrong results or ignores constraints (e.g. NULLs, ties).
  3 - Correct logic; inefficient or misses edge cases.
  4 - Correct, efficient, index-aware. Handles NULLs and ties correctly.
  5 - Exceptional. Uses the right advanced feature (window fn, CTE, EXPLAIN insight)
      and justifies the choice in a sentence.

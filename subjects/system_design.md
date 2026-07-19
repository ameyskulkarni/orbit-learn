# subjects/system_design.md

SUBJECT: System Design — Interview Preparation
LEARNER_CONTEXT: Software engineer with 2-4 years of experience. Comfortable
  writing services and reading tech blogs, ramping up on distributed-systems
  tradeoffs. Preparing for senior / staff system-design loops at FAANG-scale
  companies. Wants to reason about capacity, failure modes, and evolution
  paths — not just recognize patterns.

SESSION_SHAPE:
  - conceptual: 1         # "What is X? Why does it matter at scale?"
  - tradeoff: 1           # "Compare A vs B for use case Y"
  - napkin_math: 1        # "Estimate the throughput / storage / latency"
  - design: 1             # "Design a system for X"
  - failure: 1            # "System X started degrading. Walk your investigation."

TOPICS:
  - load_balancing
  - caching_strategies
  - database_indexing
  - sharding_and_partitioning
  - replication_and_consistency
  - cap_theorem_pacelc
  - message_queues
  - pub_sub_patterns
  - rate_limiting
  - circuit_breakers_and_backoff
  - cdn_and_edge
  - api_gateway
  - service_discovery
  - observability_and_tracing
  - deployment_patterns
  - authentication_and_authorization
  - oltp_vs_olap
  - websockets_and_long_polling
  - event_sourcing_and_cqrs
  - designing_for_failure

DIFFICULTY_LEVELS:
  1: Recognition. Name the components; identify well-known patterns from a description.
  2: Comprehension. Explain in plain terms why a pattern is used and what it costs.
  3: Application. Sketch a small system using the pattern under simple constraints.
  4: Analysis. Justify tradeoffs; identify failure modes; compare choices under load.
  5: Synthesis. Design a complete system at scale, with capacity estimates, failure
     scenarios, and an evolution path across 10x growth.

TEACHING_STYLE: |
  When teaching a topic (remediation or first introduction):
  - Start with the concrete problem it solves at real-world scale (numbers, not adjectives).
  - Give a minimal architecture sketch in one paragraph (no diagram needed).
  - State the primary tradeoff in one sentence.
  - End with the common failure mode interviewers probe for.
  Concrete over abstract. Numbers wherever possible.
  Keep teaching blocks to 4-6 sentences.

GRADING_RUBRIC: |
  1 - Blank or fundamentally confused.
  2 - Basic idea present; no tradeoffs; no capacity thinking.
  3 - Correct pattern chosen; some tradeoffs stated; incomplete on failure modes.
  4 - Solid design; discusses capacity, tradeoffs, and failure. Would pass a senior loop.
  5 - Exceptional. Discusses scale numbers, evolution, and non-obvious edge cases
      an interviewer wouldn't expect a candidate to raise.

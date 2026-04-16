# Phase 2 Closeout Summary

Short description: this file summarizes what Phase 2 improved in the retrieval layer, what was added to the MVP, and what remains for later phases.

## Phase 2 Goal

Phase 2 was about making grounded retrieval more useful, deliberate, and testable.

Phase 1 gave us a stable AI contract.
Phase 2 focused on making the evidence pipeline smarter.

The main objective was to improve:

- retrieval planning
- retrieval specificity
- bucket-aware evidence separation
- grounded guidance quality
- debug visibility
- MVP testing readiness

This phase was mainly about making Vertex-grounded retrieval behave more like an intentional subsystem instead of a simple single-query lookup.

---

## What We Locked In

### 1. Retrieval Intent Planning

We defined a controlled retrieval-intent layer for the grounded guidance flow.

This means the system can now choose focused retrieval goals such as:

- `cpr_trigger_guidance`
- `abnormal_breathing_after_fall`
- `head_injury_blood_thinners`
- `possible_spinal_injury`
- `fracture_or_cannot_stand`
- `monitor_low_risk_fall`

This matters because the agent no longer has to treat every fall as one generic retrieval problem.

---

### 2. Template-Driven Query Policy

We moved Phase 2 away from freeform query generation as the default retrieval path.

Instead:

- the backend selects intents
- intents map to controlled queries
- multiple focused queries can be issued in one run
- broad fallback queries are used only when needed

This makes the retrieval layer more stable, easier to debug, and easier to compare across scenarios.

---

### 3. Retrieval Bucketing

We defined a bucket policy so grounded snippets are grouped by purpose instead of treated as one flat list.

The Phase 2 bucket vocabulary now includes:

- `red_flags_and_escalation`
- `immediate_actions`
- `do_not_do_warnings`
- `bystander_instructions`
- `cpr_or_airway_steps`
- `monitoring_and_followup`
- `scene_safety`

This matters because reasoning, instructions, and warnings should not all pull from the same raw evidence pool.

---

### 4. Bucket-Aware Retrieval Separation

We extended Phase 2 beyond simple bucket labeling and made retrieval bucket-aware for the MVP.

That means the backend can now:

- plan retrieval by bucket, not only by intent
- issue separate queries for different grounded purposes
- return bucket-level references
- show which source was used for each bucket

This is important because `red_flags_and_escalation`, `cpr_or_airway_steps`, `bystander_instructions`, and `immediate_actions` should not all depend on one shared query by default.

---

### 5. MVP Retrieval Policy Assets

We added a machine-readable Phase 2 retrieval asset in the backend:

- `backend/data/phase2_retrieval_policy.json`
- `backend/data/phase2_bucket_query_policy.json`

This means the retrieval policy is no longer only described in `.md` files.
The MVP backend can now actually consume that policy for live retrieval planning.

---

### 6. Retrieval Engine For The MVP

We added a lightweight Phase 2 retrieval engine in the backend:

- `backend/agents/bystander/retrieval_policy.py`
- `backend/agents/bystander/retrieval_engine.py`

The MVP can now:

- detect likely retrieval signals from answers and profile
- choose top intents
- generate a small set of controlled queries
- generate bucket-specific queries for mixed cases
- retrieve grounded guidance
- bucket grounded snippets
- return bucket-level retrieval debug information

This is the first real product-facing version of the Phase 2 retrieval design.

---

### 7. Guidance Normalization

We added a normalization layer so bucketed retrieval evidence can be turned into cleaner product guidance.

The guidance flow now builds:

- `primary_message`
- `steps`
- `warnings`
- `escalation_triggers`

This matters because raw grounded snippets are not always clean enough to show directly.

---

### 8. Grounding Traceability In The MVP

The MVP response schema now includes retrieval debug fields inside grounding.

That includes:

- `retrieval_intents`
- `queries`
- `buckets`
- `queries_by_bucket`
- `references_by_bucket`
- `bucket_sources`
- grounded snippet preview
- references when available

This makes it much easier to inspect whether retrieval worked well or poorly for a given case.

---

### 9. Phase 2 Scenario Pack

We added a simple scenario pack for retrieval-focused MVP testing:

- `backend/data/phase2_test_scenarios.json`

This allows the MVP to load named cases such as:

- head injury on blood thinners
- bystander abnormal breathing case
- low-risk monitoring case

This matters because Phase 2 needed a faster loop for checking retrieval behavior, not just freeform manual testing.

---

### 10. MVP Frontend Retrieval Debug View

We extended the MVP test UI so retrieval behavior is visible during testing.

The frontend now shows:

- selected retrieval intents
- issued queries
- retrieval buckets
- bucket-specific queries
- bucket-specific references
- bucket-specific sources
- grounded preview snippets
- normalized escalation cues

This makes the MVP useful for inspecting the quality of the retrieval path before full integration.

---

## What Improved Compared To Before

Before Phase 2:

- guidance retrieval relied on a small hardcoded query choice
- retrieval behavior was mostly flat and single-purpose
- grounded snippets were not grouped by function
- raw retrieval and user-facing instructions were too tightly mixed
- the MVP did not show why a query was chosen
- testing retrieval behavior was slower and less inspectable

After Phase 2:

- retrieval is intent-based
- query construction is controlled and more repeatable
- multiple focused queries can be issued
- mixed cases can trigger bucket-specific queries
- grounded snippets are bucketed by purpose
- bucket-specific references can be inspected in the MVP
- guidance is normalized more deliberately
- retrieval choices are visible in the MVP output
- scenario-based retrieval testing is easier

---

## What Phase 2 Did Not Try To Finish

These are intentionally left for later phases:

- advanced learned reranking
- large-scale automated retrieval evaluation
- production-grade grounding analytics
- complete bystander conversation orchestration
- stronger normalization beyond simple rule-based selection
- final tuning against live Vertex datasets
- production-ready retrieval fallback calibration

Phase 2 is complete when retrieval is more deliberate and inspectable, not when the final medical-grounding system is fully optimized.

---

## Definition Of Done For Phase 2

Phase 2 should be considered complete if these are true:

- retrieval uses intent-based planning instead of one generic query
- the backend can consume a retrieval policy asset
- multiple controlled queries can be generated for one case
- mixed cases can issue separate bucket-aware queries
- grounded snippets are grouped into functional buckets
- guidance is normalized from bucketed evidence
- grounding metadata exposes intents, queries, buckets, and bucket-level references
- the MVP can load simple Phase 2 scenarios and inspect retrieval behavior

---

## Verification Completed

Phase 2 verification included:

- backend sanity checks for retrieval policy behavior
- backend sanity checks for bucketed retrieval output
- backend sanity checks for guidance normalization
- `uv run` verification for the scenario-pack route and normalization path
- frontend production build verification for the updated MVP tester
- MVP inspection showing live `vertex_ai_search` grounding with bucket-level query and reference visibility

Local verification also showed that:

- the Phase 2 retrieval path works even when Vertex AI Search is not configured
- the fallback path still returns inspectable retrieval output for MVP testing
- when Vertex AI Search is configured, the MVP can now surface live retrieval intents, issued queries, bucket-specific query plans, and bucket reference counts

---

## Recommended Next Step

The best next step after Phase 2 is not more retrieval-policy writing.

The best next step is:

- run scenario reviews through the MVP
- compare expected versus actual retrieval behavior
- refine ranking, normalization, and live Vertex grounding quality
- then move into the next layer of orchestration and production hardening

That is how we turn the new Phase 2 retrieval system into confidence for the combined backend and frontend product.

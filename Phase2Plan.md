# Phase 2 Plan

## Phase 2 Goal

Phase 2 is about making the agent use grounded medical knowledge more intelligently.

Phase 1 gave us consistency.
Phase 2 should give us stronger grounded usefulness.

The core objective is:

- retrieve the right evidence
- pass cleaner evidence into reasoning
- turn evidence into safer instructions
- make grounding visible and testable

Phase 2 should improve the quality of:

- retrieval relevance
- instruction clarity
- evidence traceability
- grounded reasoning consistency

---

## Phase 2 Scope

Phase 2 focuses on four agent-side capabilities:

- retrieval planning
- retrieval filtering and ranking
- guidance normalization
- grounding evaluation

Phase 2 should stay mostly in the AI layer.
If any backend or frontend work is done, it should be support-only and not meant to replace teammate-owned logic.

---

## What Phase 2 Is Not

Phase 2 is not mainly about:

- changing the core severity vocabulary
- redesigning the Phase 1 schema
- full bystander orchestration
- full cancellation workflow implementation
- full production dispatch integration

Those can continue later.

Phase 2 is specifically about improving how the agent uses Vertex AI Search and grounded evidence.

---

## Main Problem From Phase 1

By the end of Phase 1, the agent has a strong response contract, but retrieval is still relatively simple.

Current weak points:

- one broad query is often used
- snippets are not intentionally grouped by purpose
- the most relevant snippet may not be the most actionable one
- the same retrieval result may be used for both reasoning and user instructions without enough cleanup
- the system does not yet make grounding quality easy to inspect

So Phase 2 should make retrieval more deliberate instead of just “fetch top snippets and use them.”

---

## Phase 2 Design Principle

The Phase 2 agent should not ask:

- “What did Vertex return?”

It should ask:

- “What medical question do I need Vertex to answer right now?”

This is the shift from generic retrieval to intent-based retrieval.

---

## Phase 2 Workstreams

## 1. Retrieval Intent Planning

This is the first major Phase 2 step.

Instead of issuing one broad query, the agent should derive retrieval intents from the case.

### Examples of retrieval intents

- `fall_general_first_aid`
- `fall_red_flags`
- `head_injury_blood_thinners`
- `unconscious_after_fall`
- `abnormal_breathing_after_fall`
- `severe_bleeding_after_fall`
- `do_not_move_possible_spinal_injury`
- `bystander_check_consciousness`
- `bystander_check_breathing`
- `cpr_trigger_guidance`

### Goal

Turn event and symptom information into one or more focused retrieval targets.

### What You Should Define

- the retrieval intent vocabulary
- which red flags trigger which intents
- priority rules when multiple intents exist
- the maximum number of intents to query in one run

### Deliverable

- `Phase2RetrievalIntents.md` or equivalent intent mapping document

---

## 2. Query Construction Rules

Once intents exist, the agent needs repeatable rules for building actual queries.

### Problem

If the query wording changes too much, retrieval quality becomes unstable.

### Goal

Standardize how each intent turns into a query.

### Example Query Rules

- `fall_red_flags` -> `fall red flags emergency warning signs`
- `head_injury_blood_thinners` -> `head injury blood thinners emergency warning signs fall`
- `unconscious_after_fall` -> `unconscious patient after fall airway breathing cpr`
- `severe_bleeding_after_fall` -> `severe bleeding after fall first aid escalation`
- `do_not_move_possible_spinal_injury` -> `suspected spinal injury after fall do not move first aid`

### What You Should Define

- default query templates per intent
- when to include modifiers like elderly, blood thinners, bystander, unconscious
- when to issue one query versus multiple

### Deliverable

- a query template table for the main intents

---

## 3. Retrieval Bucketing

This is where Phase 2 becomes meaningfully better than simple RAG.

Instead of treating all snippets as equal, group retrieval outputs by purpose.

### Recommended Buckets

- `scene_safety`
- `red_flags_and_escalation`
- `immediate_actions`
- `do_not_do_warnings`
- `bystander_instructions`
- `cpr_or_airway_steps`

### Goal

Make the agent use different evidence for different output sections.

For example:

- reasoning should focus on escalation logic and red flags
- user guidance should focus on immediate actions and warnings
- bystander guidance should use bystander-specific instruction blocks

### What You Should Define

- bucket names
- which intents populate which buckets
- how many snippets each bucket can contain

### Deliverable

- a retrieval bucket policy doc

---

## 4. Snippet Ranking And Selection

Once retrieval returns multiple snippets, the agent should not use them blindly.

### Goal

Prefer evidence that is:

- directly relevant to current red flags
- operationally actionable
- specific to the patient context
- clear enough to reuse safely

### Ranking Factors

- direct symptom match
- risk-factor match such as blood thinners
- urgency relevance
- role relevance such as bystander vs patient
- instruction clarity

### Example

A snippet mentioning “head injury on blood thinners” should outrank a general “fall safety” snippet when that is the current risk.

### What You Should Define

- ranking criteria
- what makes a snippet “usable”
- when a snippet should be discarded

### Deliverable

- a ranking rubric for retrieved evidence

---

## 5. Guidance Normalization

This is one of the most important Phase 2 tasks.

Right now grounded snippets can still be too raw to show directly.

### Goal

Convert grounded evidence into clean product-ready guidance sections.

### Target Guidance Structure

- `primary_message`
- `immediate_steps`
- `warnings`
- `escalation_triggers`

### Example Transformation

Raw retrieval:

- “If not breathing or abnormal breathing, start CPR immediately.”

Normalized guidance:

- primary_message: `Check breathing immediately.`
- immediate_steps: `If the patient is not breathing normally, start CPR and use an AED if available.`
- warnings: `Do not delay emergency help if breathing is abnormal.`

### What You Should Define

- how to rewrite snippets into short instructions
- what kinds of wording are too technical
- what guidance should be excluded from direct display

### Deliverable

- guidance normalization rules

---

## 6. Grounding Traceability

Phase 2 should make grounded reasoning easier to inspect.

### Goal

Allow the team to answer:

- what query was used?
- which intent triggered it?
- which snippets were kept?
- which output fields used which evidence?

### Why This Matters

Without traceability, it becomes hard to debug whether a mistake came from:

- bad retrieval
- bad ranking
- bad reasoning
- bad instruction formatting

### Minimum Traceability Fields

- retrieval intents used
- queries issued
- source bucket for each selected snippet
- references returned
- whether fallback guidance was used

### Deliverable

- grounding trace design for debug/testing output

---

## 7. Phase 2 Evaluation Pack

Phase 2 needs a tighter evaluation loop than Phase 1.

Phase 1 asked:

- is the structure consistent?

Phase 2 should ask:

- is the grounding useful and relevant?

### Evaluation Categories

- intent selection correctness
- query relevance
- snippet relevance
- bucket assignment correctness
- guidance usefulness
- missing critical evidence
- citation/reference visibility

### Suggested Scenario Types

- head injury + blood thinners
- unconscious patient after fall
- abnormal breathing after fall
- severe bleeding after fall
- possible spinal injury
- low-risk fall with no escalation red flags
- bystander-only observation case

### Deliverable

- `Phase2GroundingTestPack.md`

---

## What You Personally Should Own In Phase 2

Since you are leading the AI side, these are the highest-value pieces for you:

- retrieval intent vocabulary
- query template design
- evidence ranking rules
- guidance normalization rules
- grounding evaluation criteria

These are the parts that define whether Vertex AI Search actually becomes a strength instead of just an attachment.

---

## What Can Be Support Work Only

If needed, these can be built as test-only support without changing teammate-owned core backend logic:

- a local retrieval sandbox script
- a test harness for evaluating queries
- a debug viewer for showing selected snippets and references
- a prototype formatter for normalized guidance output

These are useful because they let you improve the agent safely without clashing with the production path others are building.

---

## Suggested Phase 2 Execution Order

To keep Phase 2 clean, I would do it in this order:

1. Define retrieval intent vocabulary.
2. Define query templates.
3. Define retrieval buckets.
4. Define snippet ranking rules.
5. Define guidance normalization rules.
6. Build a small grounding test pack.
7. Run scenario reviews and refine.

This order helps avoid prematurely tuning prompts before the retrieval design is clear.

---

## Risks To Watch In Phase 2

### 1. Over-Retrieval

If the agent retrieves too many things, the reasoning gets noisy.

### 2. Generic Snippets Beating Specific Snippets

Broad “fall first aid” content may crowd out the more important specific protocol.

### 3. Raw Guidance Leakage

If raw snippets are shown directly too often, the app may feel messy or medically awkward.

### 4. False Grounding Confidence

The system may look grounded just because it has references, even if the wrong references were used.

### 5. Mixed Roles

Patient-facing guidance and bystander-facing guidance should not be merged carelessly.

---

## Definition Of Done For Phase 2

Phase 2 should be considered complete when:

- retrieval uses intent-based planning instead of one generic query
- evidence is grouped by function
- selected snippets are ranked more intentionally
- guidance is normalized into clearer instruction sections
- grounding trace is inspectable
- a small Phase 2 test pack can show visible retrieval-quality improvements

---

## Recommended Immediate Next Step

The best first action for Phase 2 is:

- define the retrieval intent vocabulary and query templates

That is the foundation for everything else in this phase.

If that part is weak, ranking, guidance formatting, and evaluation will all be unstable.

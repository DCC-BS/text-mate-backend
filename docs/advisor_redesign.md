# Advisor Redesign: Improving Rule-Violation Detection Rate

Status: **accepted design, phased implementation** — Phase 1 (eval harness) ships with this document.

## 1. Problem

The advisor checks a text against editorial rule collections (currently ~65 rules across
`bundeskanzlei` and `merkblatt_behoerdenbriefe`). Detection rate is unsatisfying:

- A single run misses a substantial share of real violations.
- Running the advisor repeatedly on the *same* text keeps surfacing *new* violations —
  i.e. recall per run is low and results are unstable.
- Enabling thinking on the model (Gemma, ~30B class, self-hosted on vLLM) did not help.

## 2. Diagnosis of the current pipeline

Current flow (`AdvisorService._check_text_stream`):

```
rules (sorted by collection)
  → fixed batches of 5 rules
  → per batch, sequentially: 1 LLM call: "whole text + 5 rules → list of violations"
  → resolve source snippets to char ranges (exact → lowercase → whitespace-normalized → fuzzy)
  → dedupe → stream batch results
```

Why this under-detects:

1. **Open-ended list generation caps recall.** "List all violations" lets the model stop
   whenever the list *looks* plausibly complete. LLMs systematically under-produce on
   exhaustive-enumeration tasks: after 2–3 findings the most likely next token is the
   end of the list, not a fourth finding. Nothing in the output format forces the model
   to account for every rule, every sentence, or every *occurrence* (it typically flags
   the first straight-quote and skims past the rest).
2. **Sampling variance is discarded instead of harvested.** The observation "N manual
   runs find far more than 1 run" *is* self-consistency ensembling. Each sample
   terminates its list at a different point; the union is much closer to the truth. The
   current pipeline takes exactly one sample per rule batch.
3. **One haystack size for all rules.** Mechanical rules (Guillemets, «Kurze Zahlen»,
   ß→ss, time/date formats) need *exhaustive scanning* — best done on small windows.
   Semantic rules («Roter Faden im Aufbau», «Persönliche Anrede mit "Sie"») need the
   *whole document*. Feeding the full text to both wastes attention on the mechanical
   rules and caps recall.
4. **No verification stage → the detector must be conservative.** The only precision
   lever today is the detection prompt itself, so it is implicitly tuned to avoid false
   positives, which costs recall. With a cheap downstream verifier, detection can be
   recall-tuned aggressively.
5. **Fixed batch composition, sequential execution, silent truncation.** Rules are
   always sorted and batched identically, so positional attention bias hits the same
   rules every run. Batches run sequentially against a 60 s overall timeout
   (`AGENT_TIMEOUT_SECONDS`); on slow runs the tail batches are silently dropped —
   an invisible recall loss.
6. **Lossy post-processing.** Violations whose `source` snippet cannot be located
   (hallucinated or paraphrased snippets, or snippets mutated by output postprocessing
   such as ß→ss replacement) are dropped with only a log line. Real findings die here;
   nothing measures how many.

## 3. Decisions (from design interview, 2026-07-07)

| Question | Decision |
|---|---|
| LLM call budget | Parallel calls against self-hosted vLLM are fine (50–150 calls/check OK if wall-clock stays reasonable, streaming as results arrive). |
| Precision/recall balance | **Recall first.** Occasional dismissible false flags are acceptable; misses are worse. |
| Hybrid deterministic checkers | **Yes.** Mechanical rules may be compiled to deterministic checkers (regex/code), generated offline and human-reviewed, stored alongside the rule data. |
| Precision mechanism | **Voting + verifier.** Auto-accept high-agreement ensemble candidates; send low-agreement candidates through a binary LLM judge. |
| API/SSE contract | Free to change; frontend is being redesigned. |
| Second model | Possible — a small model (~4B) can be deployed next to Gemma to serve verifier traffic. |
| Evaluation | Build a synthetic eval set + harness first; tune everything empirically. |

## 4. Target architecture

```
                       OFFLINE (rule pipeline, extends text_mate_tools)
  PDF → docling → extract rules → consolidate → classify(kind, scope) → generate checkers
                                                       │                     │
                                              rules/*.json (enriched)   checkers/*.json
                       ─────────────────────────────────────────────────────────────
                       RUNTIME (per check request)

  text ──► Stage 1: deterministic pass          rules with checker → violations (confidence: certain)
       │            (regex/code, instant, 100% recall for covered rules)
       │
       ├─► Stage 2: LLM detection (recall-tuned, all calls in PARALLEL)
       │      routing by rule.scope:
       │        window-scoped rules  × text chunks (paragraph windows)
       │        document-scoped rules × whole text
       │      per (rule-batch × chunk) cell: K samples, temp > 0, shuffled rule order
       │      output format: per-rule checklist verdict + ALL occurrences
       │
       ├─► Stage 3: aggregation & voting
       │      canonicalize (resolve char spans, existing _find_source logic)
       │      cluster candidates by (rule, overlapping span)
       │      agreement = fraction of the K samples that found the cluster
       │        agreement ≥ T_accept  → accept (confidence: high)
       │        agreement < T_accept  → forward to Stage 4
       │
       ├─► Stage 4: verification (small model, parallel)
       │      binary judge per candidate: rule + snippet ± context → violates? yes/no
       │      yes → accept (confidence: verified);  no → drop
       │
       └─► Stage 5: emission (SSE)
              violations stream out as soon as they are FINAL (never revised):
              certain (immediately) → high (after voting) → verified (after judging)
```

### 4.1 Stage 0 — offline rule enrichment

Extend `Rule` with three optional fields (backwards compatible — defaults preserve
current behaviour):

```python
kind: Literal["mechanical", "lexical", "semantic"] = "semantic"
scope: Literal["window", "document"] = "document"
checker: CheckerSpec | None = None  # e.g. {"type": "regex", "pattern": "ß", "message_template": ...}
```

- `kind` drives prompt selection and ensemble size (mechanical rules need more
  exhaustive scanning; semantic rules need fewer, larger-context samples).
- `scope` drives routing: `window` rules are checked per text chunk, `document` rules
  against the full text.
- `checker` marks a rule as deterministically *triggerable*. Checker execution is a
  small, safe interpreter (regex + optional exception list), **not** arbitrary code.

**Trigger–judge, not regex-decides.** Many mechanical rules interact with sibling rules
or carry exceptions, so a regex alone cannot be the verdict. Example: «Kurze Zahlen im
Fliesstext ausschreiben» (digits ≤ 12 should be words) is suspended by «Mehrere Zahlen
im gleichen Zusammenhang in Ziffern» (in comparisons/enumerations, *all* numbers stay
digits), and by Sonderregeln for Masse, Geldbeträge and Fristen. The robust split:

- The **trigger** is tuned for 100% recall on the surface pattern and *never decides*:
  a digit 0–12 in running text, a `\d{1,2}:\d{2}` time, a straight quote, a mixed
  Zahlwort-plus-Ziffer sentence. Deterministic, so no occurrence is ever skimmed past —
  this eliminates the LLM's first-hit-only failure mode for these rules.
- The **judge** is a focused LLM call per triggered span: the sentence context, the
  triggering rule *and its interacting sibling rules / exceptions* (declared per checker
  spec), question: "violation or exception?". Rules whose checker declares
  `decides: true` (no exceptions possible, e.g. «Doppel-s statt Eszett (ß)» — every ß is
  a violation) skip the judge entirely.

So «Es wurden 3 Eingaben gemacht.» → trigger fires on «3» → judge sees no comparison,
no Sonderregel → violation. «Die Frist beträgt sieben Tage, bei Verträgen 14 Tage.» →
the mixed-usage trigger fires → judge attributes it to the *sibling* rule (Zahlwort
«sieben» must become «7») → violation of the correct rule. A pure-LLM pass misses
occurrences; a pure-regex pass gets the exceptions wrong; trigger+judge gets recall from
the machine and judgment from the model.

Classification and checker drafting are done by an offline LLM pass (a new
`text_mate_tools` script, same staging-and-review workflow as rule extraction). Humans
review before merge — a wrong regex is a systematic error, so review is mandatory.

Trigger-eligible rules in the current set: «Doppel-s statt Eszett (ß)» (decides),
«Guillemets als Anführungszeichen» (decides, modulo apostrophe handling), «Uhrzeit mit
Punkt» (decides), «Datum … ausgeschriebenem Monat», «Jahreszahlen vierstellig», «Grosse
Zahlen in Dreiergruppen», the number-word family (judged). Roughly a third of the
bundeskanzlei collection is triggerable — those rules get deterministic recall and at
most one cheap judge call per occurrence, freeing the LLM budget for the semantic
rules.

### 4.2 Stage 2 — detection

Changes relative to today, in order of expected recall impact:

1. **Ensembling (K samples per cell).** Same input, `temperature ≈ 0.8`, K=3–5
   (tunable, start K=3 for semantic / K=5 for mechanical-without-checker). Fired
   concurrently via `asyncio.gather`; `BaseAgent.run` already accepts per-call
   `model_settings`, so temperature/seed need no framework change.
2. **Checklist-forced output.** The output schema changes from "list of violations" to
   *per rule in the batch*: `rule_name`, `verdict: violated | not_violated`,
   `findings: [...]`. The model must account for every rule explicitly — it can no
   longer end the list early without visibly skipping a rule. The prompt additionally
   demands *every occurrence*, with a few-shot example containing three occurrences of
   the same rule.
3. **Chunking for window-scoped rules.** Split text into paragraph windows of ~600–900
   chars with one-sentence overlap; run window-scoped rule batches per window. Small
   haystacks make exhaustive scanning tractable for a 30B model. Document-scoped rules
   keep the whole text.
4. **Shuffled rule order per sample.** Batches are composed once per request, but the
   rule order *within* the prompt is shuffled per sample, so positional bias averages
   out across the ensemble instead of hitting the same rules every time.
5. **Smaller batches (3–4 rules).** With parallelism, batch size no longer trades
   against latency; smaller batches sharpen per-rule attention.
6. **Per-call timeouts instead of one global timeout.** Every cell gets its own
   timeout; a slow cell costs that cell only. Cells that time out are *reported* in the
   progress stream (`skipped` counter), never silently dropped.

### 4.3 Stage 3 — voting

Candidates from all samples of a cell are canonicalized (span resolution reuses
`_find_source`) and clustered by `(rule, overlapping span)`. Agreement = |samples
containing the cluster| / K.

- `agreement ≥ T_accept` (default 0.6): accept without verification.
- `0 < agreement < T_accept`: forward to Stage 4. This is precisely where the
  "run-it-again finds more" findings live — rare-but-real detections that today only
  appear on lucky runs. They are no longer lost; they are cheap-verified.

### 4.4 Stage 4 — verification

One short call per low-agreement candidate: rule name + description + example, the
snippet with ±1 sentence of context, question "Verstösst dieser Ausschnitt gegen diese
Regel? yes/no". Strict binary output, `temperature 0`, thinking off. Routed to the small
secondary model (~4B) when deployed; falls back to the main model otherwise (the calls
are short, so overhead on Gemma is modest). Verification calls run in parallel.

Recall-first tuning: `T_accept` and the verifier prompt are the two precision knobs; the
eval harness (§6) measures precisely what each setting costs in recall.

### 4.5 Stage 5 — streaming contract (breaking change, coordinated with frontend redesign)

Today: a stream of `RulesValidationContainer {violations, checked, total}`; emitted
violations are final, progress = rules checked. Proposed JSON-lines events:

```jsonc
{"event": "progress", "stage": "detection", "done": 12, "total": 40, "skipped": 0}
{"event": "violation", "violation": {…ViolationResult…, "confidence": "certain|high|verified"}}
{"event": "done", "summary": {"violations": 17, "cells_skipped": 1}}
```

Rules:
- A `violation` event is final — the UI never has to retract a shown flag.
  (Verification happens *before* emission, not after.)
- `progress.total` counts pipeline cells, not rules, so the bar moves honestly.
- `confidence` lets the UI display certainty (e.g. deterministic findings styled
  differently from verified single-sample findings).

### 4.6 Cost model (65 rules, ~1 page of text)

| Stage | Calls | Notes |
|---|---|---|
| Deterministic | 0 | ~20 rules covered by checkers |
| Detection | ≈ (45 LLM rules / 3–4 per batch) × chunks(≈3 for window rules, 1 for document rules) × K(3–5) ≈ **80–120** | all parallel; wall-clock ≈ a few sequential-call latencies given vLLM batching |
| Verification | ≈ 5–20 (only low-agreement candidates) | short calls, small model |

Today: ~13 sequential calls, often 60s+. Target: more total compute, but *parallel* —
wall-clock comparable or better, and progress streams from the first finished cell.

## 5. Prompt changes (Stage 2 detection prompt)

Keep from the current prompt: exact-snippet copying rules, minimal-span instruction,
answer-in-text-language, Swiss orthography examples. Change:

- Checklist output (see §4.2.2) — one verdict per rule, findings nested under it.
- Explicit exhaustiveness contract: *«Melde JEDES Vorkommen eines Verstosses, auch wenn
  derselbe Fehler mehrfach vorkommt. Zwei gleiche Fehler = zwei Meldungen.»* with a
  few-shot example showing 3 findings for one rule in one short text.
- For window-scoped calls: the prompt states the window is an excerpt and rules about
  document structure don't apply (those are document-scoped anyway).
- Recall-first framing: *«Melde einen Verstoss auch dann, wenn du unsicher bist»* —
  the voting/verification stages own precision, the detector owns recall.

## 6. Evaluation harness (ships with this document — Phase 1)

Detection rate becomes a measured number, not a feeling. Components:

- **Eval cases** (`evals/advisor/cases/*.json`): texts with exhaustively labeled
  ground-truth violations (`rule_name`, exact `source` substring, `occurrence` index for
  repeated substrings, optional `alt_rule_names` where sibling rules legitimately
  overlap, e.g. «Kurze, einfach gebaute Sätze» vs «Ein Gedanke pro Satz»). Includes
  multi-occurrence cases (the known first-hit-only failure mode) and a clean negative
  case (false-positive floor).
- **Scorer** (`text_mate_tools.advisor_eval.scoring`): greedy one-to-one matching of
  predictions to expected via rule name + span overlap. Reports per-rule and overall
  precision/recall/F1, plus *rule confusions* (span found, wrong rule cited) via a
  lenient span-only pass — this separates "didn't see it" from "saw it, misattributed".
- **Runner** (`text_mate_tools/run_advisor_eval.py`): drives the real `AdvisorService`
  against the cases, `--runs N` for multi-run analysis:
  - *single-run recall* (mean ± spread) — today's user experience,
  - *union recall* across N runs — the ensemble headroom (what §4.2.1 will capture),
  - *stability* (mean pairwise Jaccard of found-violation sets) — run-to-run consistency.
  The union-vs-single-run gap is the direct measurement of the "run it again, find more"
  effect, and the primary number the redesign must close.
- **Case generator** (`text_mate_tools/generate_eval_cases.py`): LLM-assisted seeding of
  violations for a given rule set into realistic Behörden texts, written to `staging/`
  for mandatory human review (same workflow as rule extraction).

Workflow: baseline the current pipeline → implement a phase → re-measure → tune knobs
(K, T_accept, batch size, chunk size) against the numbers.

## 7. Migration plan

| Phase | Content | Schema/API impact |
|---|---|---|
| **1 (this PR)** | Eval harness + seed cases + baseline measurement | none |
| **2** | Parallel cells, per-cell timeouts, ensemble K samples, voting, verifier; checklist output format; shuffled rule order | none (existing SSE shape can carry it) |
| **3** | Rule enrichment (`kind`, `scope`) via offline classification pass; chunked routing for window rules | rule JSON additive |
| **4** | Deterministic checkers: offline generation tool + safe runtime interpreter | rule JSON additive |
| **5** | New streaming contract with stage progress + confidence | breaking, coordinated with frontend redesign |

Phase 2 is the highest expected win per effort (it directly harvests the variance the
user already observed) and needs no data or contract changes.

## 8. Configuration knobs (added as tuning proceeds)

`ensemble_k_mechanical`, `ensemble_k_semantic`, `detection_temperature`,
`accept_agreement_threshold`, `rules_per_batch`, `chunk_size_chars`, `chunk_overlap`,
`cell_timeout_seconds`, `verifier_model` (falls back to `llm_model`),
`max_parallel_llm_calls` (semaphore protecting vLLM).

## 9. Open questions

- Gemma structured-output + thinking interaction: vLLM guided decoding can suppress the
  benefit of thinking. Worth an eval-harness A/B: thinking on/off × structured output vs
  two-step (free-form findings, then a formatting call).
- The ß→ss output postprocessor (`replace_eszett` in `BaseAgent`) can mutate `source`
  snippets so they no longer match the input text (e.g. rule «Doppel-s statt Eszett»).
  The eval set contains a case for this; likely fix: exempt `source` fields from output
  postprocessing and normalize during span resolution instead.
- Whether verification should see the *full* rule list to re-attribute a finding to the
  correct sibling rule (fixing rule confusions instead of just dropping them).

# Simplify Redesign: readability-gated iterative simplification

Status: **accepted design, implemented** — companion to [`advisor_redesign.md`](./advisor_redesign.md).

## 1. Context & Problem

The previous `plain_language` quick action rewrote Behörden text into Einfache Sprache (B1–A2) with a **single LLM call and no verification**. Nothing checked that the output was actually simpler, and nothing checked that it still said what the source said. The backend computed a trained German readability score (ZIX → CEFR) but only as a passive UI badge. There was also no language detection.

Furthermore, the prompt asset (`easy_language.py`, Canton of Zurich derived) contained typography rules that **contradicted** Basel-Stadt and Bundeskanzlei rules enforced by our advisor.

**Goal:** Transform simplification into a **measured, closed-loop, language-aware** pipeline. Text language is detected, scored with an appropriate metric, rewritten, and re-scored with numbers surfaced to the user and the eval harness.

## 2. Key Decisions & Rationale

| Decision | Choice | Rationale & Trade-offs |
|---|---|---|
| **Workflow orchestration** | Deterministic Python pipeline | Orchestrator owns the loop and decisions; LLM only rewrites. |
| **Language detection & fallback** | `fast-langdetect` | Detection on full text overrides client UI locale. Unsupported languages (`!= de, en, fr, it`) fall back to single-shot generic rewrite without fake scores. |
| **Metrics per language** | `de` → ZIX (trained)<br>`en` → FRE → CEFR<br>`fr` → LIX<br>`it` → Gulpease | Language-specific metrics with calibrated `easy` bands (ported from `blokkli/editor`). No WSTF for German (ZIX accounts for vocabulary difficulty). |
| **Rule asymmetry** | Tailored for `de`; generic for `en/fr/it` | German uses a reconciled Basel-Stadt style block (`utils/simplify_style.py`). Other languages use language-neutral instructions (`utils/simplify_generic.py`) to avoid inventing unreviewed administrative style guides. |
| **Unit chunking & merging** | Merge paragraphs to ≥100 words | Raw paragraphs (~35 words median) have ~1.8 ZIX noise against 2.0-wide bands. Merging to ≥100 words reduces measurement error to well under half a band. Headings and list items act as unmerged barriers. |
| **Mode threshold** | 10,000 chars | ≤10k chars runs WHOLE document mode in 1 call. >10k chars runs CHUNKED mode unit-wise (avoids degraded quality over very long single generations). |
| **Attempts & retries** | 1 pass + 1 retry round (max 2 attempts) | Diminishing returns from a 3rd attempt on real documents. Failing units in pass 1 are retried in parallel. |
| **Per-unit gating vs. single displayed score** | Gating is per-unit; display is whole-document | Gating per-unit prevents dense clauses from hiding in whole-document averages. The user UI displays only the whole-document score to avoid confusing conflicting metrics; shortfall passages are flagged via `unconverged_ranges`. |
| **No runtime fidelity gate** | Prompt discipline + eval measurement | A runtime LLM fidelity gate was tested, found flaky, false-flagged valid digit conversions (e.g. "dreissig" → "30"), and doubled call costs. Information preservation is enforced via prompt (`REWRITE_COMPLETE`) and measured in evals. |
| **Best-attempt resolution** | Keep best raw score | If a unit improves (e.g. C2 → B2) but misses the `easy` target, keep the improved attempt rather than reverting to the original or failing. |
| **No backend diffing** | Frontend owns diffing | The Nuxt UI (`DiffViewer.vue`) handles word-level diffing and per-hunk accept/reject. Backend returns final assembled text. |

## 3. Target Architecture & Pipeline

```
POST /simplify  { text, language? }
  │
  ├─ Stage 0: Detect & Classify
  │    lang = detect_language(text)
  │    analyzer = get_analyzer(lang)
  │    if analyzer is None:
  │         → single-shot generic rewrite, no scoring/loop, emit done(scored=false)
  │    units = split_units(text) → merge_units(units, min_unit_words=100)
  │    mode = WHOLE if len(text) <= 10000 else CHUNKED
  │
  ├─ Stage 1: Initial Measurement
  │    score(text) + score_many(units)
  │    emit {event: "start", language, score_label, mode, units, score_before, ...}
  │
  ├─ Stage 2: Pass 1 (Rewrite)
  │    WHOLE: rewrite full text in one call
  │    CHUNKED: rewrite failing merged units concurrently (bounded by semaphore)
  │    score resulting units; in CHUNKED mode emit "chunk_done" per finalized unit
  │
  ├─ Stage 3: Pass 2 (Retry failing units)
  │    Identify units still outside target band
  │    If any fail: rewrite failing units concurrently with retry prompt (issue list + exemplars)
  │    Score retries and select best attempt per unit by raw score
  │
  └─ Stage 4: Assembly & Emission
       Reassemble document (1-in-N-out preserved), compute whole-document score
       emit {event: "done", text, score_before, score_after, converged, unconverged_units, unconverged_ranges}
```

### 3.1 Streaming Wire Contract (`POST /simplify`)

JSON Lines streaming response (`X-Accel-Buffering: no`):

```jsonc
{"event":"start","language":"de","score_label":"ZIX","scored":true,"mode":"whole","units":12,"score_before":-3.8,"band_before":"hard","cefr_before":"C1"}
{"event":"progress","attempt":1,"stage":"rewriting"}
{"event":"progress","attempt":1,"stage":"readability","score":-0.8,"band":"ok","cefr":"B2","units_in_target":10}
{"event":"chunk_done","index":3,"text":"...","score_before":-4.1,"score_after":1.2,"cefr_before":"C1","cefr_after":"A2","attempts":1,"converged":true} // CHUNKED only
{"event":"done","text":"...","language":"de","score_label":"ZIX","scored":true,"score_before":-3.8,"score_after":1.4,"band_after":"easy","cefr_after":"A2","converged":true,"unconverged_units":[],"unconverged_ranges":[]}
```

- `units`, `units_in_target`, and `unconverged_units` all describe merged, scorable units (never raw blank-line blocks).
- `chunk_done` is final for that unit.
- `done` always carries the complete assembled text.

## 4. Readability Module (`readability/`)

Separates language-agnostic scoring mechanics from per-language calibrations behind a unified `ReadabilityAnalyzer` Protocol:

```
readability/
  __init__.py          # Public API: detect_language, get_analyzer, ReadabilityAnalyzer
  types.py             # LanguageCode, ReadabilityBand, ReadabilityScore, Protocol
  detection.py         # fast-langdetect wrapper with confidence thresholds
  registry.py          # LanguageCode -> ReadabilityAnalyzer mapping
  core/                # Language-agnostic: tokenization, formulas (FRE, LIX, Gulpease), band mapping
  languages/           # Language-specific implementations
    german.py          # ZIX-backed analyzer, CEFR mapping, min_words=6
    english.py         # Flesch Reading Ease (pyphen syllables) -> CEFR mapping
    french.py          # LIX formula analyzer
    italian.py         # Gulpease formula analyzer
```

## 5. Prompt Design & House Style

- **German Rule Reconciliation (`utils/simplify_style.py`):** Audit of `RULES_ES` against `bundeskanzlei.json`, `merkblatt_behoerdenbriefe.json`, and `BASEL_STADT_HOUSE_STYLE`. Contradictions removed (e.g. Zurich's `.00` time requirement replaced by Bundeskanzlei `14 Uhr`; Zurich's written-out units replaced by standard abbreviations `30%`, `CHF`/`Fr.`).
- **Prompt Components (`utils/simplify_prompt.py`):** Modular prompt renderer assembling:
  1. *House Style & Rules* (`SIMPLIFY_STYLE_DE` or `GENERIC_SIMPLIFY_INSTRUCTIONS`).
  2. *Score Reference Table* (calibrated bands for the active language).
  3. *Issue List & Escalation* (on retry: quoting failing passages with targeted simplification advice).
  4. *Passing Exemplars* (up to 2 in-target paragraphs from the same document).
  5. *Chunk Context* (in CHUNKED mode: read-only previous/following paragraphs).

## 6. Evaluation Methodology & Corpus

- **Corpus (`evals/simplify/cases/*.json`):** 16 cases, including 12 real published Basel-Stadt Grosser-Rat documents (Anzüge, Ratschläge, Berichte, Initiativen) ranging up to 38k characters.
- **Metrics (`src/text_mate_tools/run_simplify_eval.py`):**
  - Primary: *Documents-in-target rate* (whole assembled text reaching `easy`).
  - Secondary: *Units-in-target rate*, score delta, CEFR shift, length ratio.
  - Fidelity: Must-keep facts preservation (normalized comparison in `simplify_eval/normalize.py`).

## 7. Empirical Validation Summary

Comparison on the 16-case Basel-Stadt corpus between `main`'s single-shot baseline and the redesign loop:

| Metric | `main` Single-Shot | Redesign Loop | Analysis |
|---|---|---|---|
| **ZIX Score After** | +0.84 ± 0.66 | +0.81 ± 0.79 | Both reach target level on aggregate |
| **Documents in Target (`easy`)** | 14/16 | 12/16 | Comparable headline readability |
| **Length Ratio (All Modes)** | 0.72 | **1.04** | Baseline achieves score by truncating |
| **Length Ratio (Long Docs)** | **0.50** | **1.11** | Baseline deletes ~50% of long texts |
| **Must-Keep Facts Lost** | **48** (in 12/16 docs) | **19** (in 9/16 docs) | Redesign preserves critical legal citations, dates & numbers |
| **Hyphenated Compounds** | 5.41 / 1k chars | **1.01** / 1k chars | Reconciled rules prevent excessive A1-style hyphenation |
| **Blind LLM Judge Preference** | 11 | **39** (14 ties) | Strong preference across Citizen, Legal, and Admin roles |

**Key Finding:** Single-shot simplification maximizes readability scores on long documents by discarding up to half the content (Geschäftsnummern, dates, budget codes). The redesign loop enforces structural completeness and fact retention while achieving the target readability band.

# Simplify Redesign: readability-gated iterative simplification

Status: **accepted design, phased implementation** — Phase 1 (eval harness) ships with this document.

Companion to [`advisor_redesign.md`](./advisor_redesign.md), whose structure and
eval-first discipline this document deliberately mirrors.

## 1. Context

The `plain_language` quick action rewrites Behörden text into Einfache Sprache (B1–A2)
with a **single LLM call and no verification of any kind**. Nothing checks that the output
is actually simpler, and nothing checks that it still says what the source said. The
backend already computes a trained German readability score (ZIX → CEFR) but it is wired
only to a passive badge in the UI — the simplifier and the scorer have never met. There is
also no language detection anywhere: `quick_action_service.py:64` parses a
`"language code:<x>"` hint out of the client's `options` string (the **UI locale**, not the
text's language) and `agent_utils.py:4` turns it into a single prompt line.

The prompt asset itself is strong (`easy_language.py`, 416 lines, Canton of Zurich
derived) but half of it is dead code, and its Zurich typography rules **contradict** the
Basel-Stadt / Bundeskanzlei rules our own advisor enforces — so the tool can produce text
that the tool then flags.

Intended outcome: simplification becomes a **measured, closed-loop, language-aware**
operation. The text's language is detected, it is scored with a language-appropriate
metric, rewritten and re-scored — with the numbers surfaced to the user and to an eval
harness.

### 1.1 Where the ideas come from

**`blokkli/editor` (dev, MIT)** — the agentic readability workflow:

| Idea | Location | Take? |
|---|---|---|
| Measure → rewrite → re-measure → retry, feeding back previous attempt + remaining issues + *passing* exemplars | `agent/runtime/app/tools/delegate_text_rewrite/useFieldRewriteStream.ts` `readabilityRetryLoop()` | **Yes — the core idea** |
| Per-language analyzer contract with calibrated bands, impact thresholds, min-words and reference tables | `readability/runtime/analyzers/builtin.ts` `SCORE_CONFIGS` | **Yes — §4.2** |
| FRE→CEFR (`en`), LIX (`fr`), Gulpease (`it`) formulas + tokenization | same file | **Yes, ported** |
| Score-reference table rendered into the rewrite prompt | `getAgentContext()` | **Yes** |
| Structured issue list per unit: `Field N: "<text>" [impact, score]` | `server/templates/definitions/fixReadability.ts` | **Yes**, as per-paragraph diagnostics |
| Escalating retry instructions ("max 10-12 words per sentence") | same template | **Yes** |
| Language-neutral rewrite instructions for the generic case | same template | **Yes — §5.4** |
| Human approval with before/after scores | `delegate_text_rewrite/Component.vue` | **Yes** — we have `DiffViewer.vue` |
| `SEARCH/REPLACE` protocol + `FieldStreamParser` | `server/classes/FieldStreamParser` | **No** — §4.5 |
| Wiener Sachtextformel for German | `builtin.ts` `WSTF_VARIANT_1` | **No** — ZIX is better, §2.1 |
| German syllable heuristic `countSyllablesDe` | same file | **No** — only WSTF needs it |
| Fixed, non-adjustable target | `SCORE_CONFIGS` bands | Matches our single-target decision |

Blokkli has **no** fidelity check, **no** target-level control, and **no** evals.

**`machinelearningZH/simply-simplify-language{,_api}` (MIT)** — the origin of our
`easy_language.py` (identical `template_es` / `rules_es` / `rewrite_complete` /
`system_message_es`). The API version is one `chat.completions.parse` call with no
scoring. The Streamlit app scores with ZIX and *displays* the number, but nothing feeds
back. Their `config.yaml` gives us calibrated German targets:

```yaml
understandability:
  limit_hard: 0
  limit_medium: -2
  metric_help: "... Texte in Einfacher Sprache haben meist einen Wert von 0 bis 4 oder höher ..."
```

**Neither project closes the loop.** That combination — a readability gate plus retry — is
what this document specifies. (A fidelity gate was also specified, built, measured and then
removed; see §4.6 and §13.1.)

## 2. Current state (verified)

### 2.1 Scoring

`services/text_analysis_service.py` (22 lines, entire file) calls
`zix.understandability.get_zix` / `get_cefr`. ZIX is a **trained model**, not a hand
formula: spaCy `de_core_news_sm` features (mean sentence length, RIX, CEFR-vocab coverage
against a Swiss-German lemma table, common-word score) → StandardScaler → ridge regressor
→ score clipped to [-10, 10]. German-only by construction.

`get_cefr`: `>=4.0 A1`, `>=2.0 A2`, `>=0 B1`, `>=-2 B2`, `>=-4 C1`, else `C2`.
So **CEFR ∈ {A1, A2, B1} ⇔ ZIX ≥ 0** — identical to ZH's "easy" floor.

ZIX beats blokkli's WSTF for German because it has vocabulary difficulty in its feature
set; WSTF counts only syllables and word length and is trivially gamed by chopping
sentences in half. Hence ZIX stays the German analyzer and WSTF is not ported.

Gaps: no `try/except` (ZIX raises `ValueError` above 1M chars, warns below 5 words →
currently a 500 via `handle_exception`), no length guard, no caching, no batch API.

### 2.2 Simplification

`agents/agent_types/quick_actions/plain_language_agent.py` (59 lines): single-shot
streaming, `enable_thinking=False`. Registers a `check_readability_score` tool computing
`text.split()` counts — **nothing in the instruction ever tells the model to call it**,
and its output feeds nothing. Class docstring says "Leichte Sprache" while the prompt set
is ES (B1–A2).

`utils/easy_language.py`: only `SYSTEM_MESSAGE_ES`, `CLAUDE_TEMPLATE_ES`,
`REWRITE_COMPLETE`, `RULES_ES` are imported anywhere. **Dead:** all `*_LS` constants
(incl. `RULES_LS`), both `CLAUDE_TEMPLATE_ANALYSIS_*`, all `OPENAI_TEMPLATE_*`,
`REWRITE_CONDENSED`, and all five helper functions.

### 2.3 The rule conflict

`RULES_ES` is Zurich-derived. `utils/house_style.py` (`BASEL_STADT_HOUSE_STYLE`) and
`assets/docs/rules/{bundeskanzlei,merkblatt_behoerdenbriefe}.json` (51 + 14 rules) are
what our advisor enforces. Confirmed contradictions:

| Topic | `RULES_ES` | `bundeskanzlei.json` |
|---|---|---|
| Null-Rappen | «.00» oder Dezimalstellen weglassen | *"fehlende Rappen mit **Gedankenstrich**"* → `CHF 20.—` |
| Einheiten | «30 Prozent» statt «30 %», «2 Meter» statt «2 m» | *"Masse, Gewichte und Währungen mit **abgekürzter Einheit** in Ziffern"* |

Assume more exist; §5.1 requires a full audit. `BASEL_STADT_HOUSE_STYLE` item 5 already
states *"Übernimm alle Fakten (Daten, Fristen, Namen, Beträge) exakt und unverändert"* —
the fidelity requirement exists as prose today, just unverified.

### 2.4 Infrastructure already in place

- `BaseAgent` (`dcc_backend_common`) supports per-call `model_settings` (temperature),
  structured output, streaming, tenacity retries. **No framework change needed.**
- Concurrency + per-cell timeouts + cancel-on-disconnect: `services/advisor.py` `run_batch`.
- JSONL streaming contract + client parser: `POST /advisor/validate` ↔
  `app/composables/useAdvisor.ts:80-200`.
- **Diffing and approval, complete:** `app/utils/diffSegments.ts` (`diffWordsWithSpace`,
  adjacent-change merging, whitespace suppression) + `app/components/diff/DiffViewer.vue`
  (556 lines: per-hunk accept/reject, inline + split, bulk actions, `getResolvedText()`).
- Eval scaffolding: `evals/advisor/cases/`, `advisor_eval/scoring.py`, `run_advisor_eval.py`.
- Client sends **plain text**: `useBaseEditor.ts:70` uses `editor.getText()`, blocks
  separated by `\n\n`. Editor limit 100,000 chars (`WorkspaceContainer.vue:206`) ≈ 30K
  tokens — inside the 50K working budget on a 256K-context model. **Context is never the
  binding constraint; output generation length is.**

## 3. Decisions (design interview)

| Question | Decision |
|---|---|
| Workflow shape | **Deterministic Python pipeline.** Orchestrator owns the loop; the LLM only rewrites. |
| Target levels | **One target only.** No ES/LS selector, no completeness switch. Do not add user choices. |
| Language | **Detected from the text** (`fast-langdetect`), once per request, whole text. Detection **overrides** the client's UI-locale hint. |
| Metric | **Per language.** `de` → ZIX/CEFR (as today). `en` → Flesch Reading Ease → CEFR. `fr` → LIX. `it` → Gulpease. Formulas and calibrated bands ported from blokkli. |
| Target | The analyzer's calibrated **`easy` band**. For German that is CEFR A2/B1 — what `SYSTEM_MESSAGE_ES` already asks for. |
| Ranking | Gate on the band; **rank attempts on the raw score** (bands are coarse). |
| Unknown language | **No scoring, no loop** — single-shot rewrite, returned with no score. Do not fake a number. |
| Non-German rewrite rules | **Generic, language-neutral simplification prompt** + that language's score reference. No house style, no typography rules (we have not authored those for en/fr/it). |
| Rewrite unit | **Whole text by default.** Chunking only above **8,000 chars**. Chunking costs context, so it is the exception. |
| Diagnostics | **Always score per paragraph**, both modes. Local CPU call, nearly free, and it is what makes the retry prompt specific. |
| Chunked-mode context | Neighbour paragraphs supplied **read-only**; rewrite scoped to the target paragraph. |
| Structure | **1 unit in, N paragraphs out.** Splitting a paragraph is the most effective simplification move. |
| Output format | **Full rewritten text.** No SEARCH/REPLACE, no patch protocol, no backend diffing — the Nuxt UI already diffs. |
| Fidelity | ~~Second gate inside the loop~~ → **no fidelity gate.** Reversed on measured evidence; see §4.6 and §13.1. |
| Attempts | **Max 3.** Keep the **best-scoring attempt**, never blindly the last. If none reaches target, keep the **original** and mark it unconverged. |
| `converged` | **Mode-independent:** "the assembled text reached the target band". Per-paragraph shortfall is reported separately via `unconverged_paragraphs` (§13.2). |
| Rule authority (de) | **Basel-Stadt / Bundeskanzlei wins.** Strip contradicting ZH typography rules from `RULES_ES`. |
| Tone block | **Hand-curated, human-reviewed module.** No runtime rule injection, no offline LLM synthesis. |
| Advisor gate | **No third gate.** Fix the contradiction at the prompt level instead. |
| Chunker | **Simplify-local for now**, unified with the advisor later (§4.4). |
| API | **New `POST /simplify`**, JSONL events, same shape as `/advisor/validate`. |
| Frontend | Wire `plain_language` button to `/simplify`, show progress, hand result to the **existing** `DiffViewer`, add before/after score to the header. |
| Old action | **Replaced.** `PlainLanguageAgent` becomes the loop's internal rewriter. |
| Eval | **Phase 1**, before touching the pipeline. Corpus = real public Basel-Stadt texts (German). |

## 4. Target architecture

### 4.1 Pipeline

```
POST /simplify  { text }
  │
  ├─ Stage 0  lang = detect(text)                    fast-langdetect, whole text, once
  │           analyzer = registry.get(lang)          None when lang ∉ {de,en,fr,it}
  │           if analyzer is None:
  │                → single-shot rewrite, no scoring, no loop, emit done(scored=false)
  │
  │           paragraphs = split(text, "\n\n")       classify heading / list / paragraph
  │           mode = WHOLE if len(text) <= 8000 else CHUNKED
  │
  ├─ Stage 1  score(text) + score_many(paragraphs)   threadpool, memoized
  │             emit {event: start, language, score_label, mode, …}
  │
  ├─ Stage 2  LOOP, attempt = 1..3
  │
  │   MODE WHOLE  (the default path)
  │     2a rewrite(ENTIRE text)        full context, one call
  │          prompt: language-appropriate rules (§5.4), whole-text score + band,
  │          score reference table, per-paragraph issue list from attempt 2
  │     2b score(result) + score_many(its paragraphs)
  │     pass when band == easy
  │
  │   MODE CHUNKED  (> 8,000 chars only)
  │     failing = paragraphs whose band != easy
  │     2a rewrite(each failing paragraph) CONCURRENTLY, semaphore-bounded
  │          prompt adds: previous + following paragraph READ-ONLY, one-line document
  │          summary, "rewrite ONLY the target paragraph"
  │     2b score(each rewrite)
  │     a paragraph finalizes when band == easy
  │          → emit {event: chunk_done, index, …} immediately (never retracted)
  │
  │   both modes: record every attempt (text, score, band)
  │
  ├─ Stage 3  resolve non-convergence   best-scoring attempt;
  │                                     else the ORIGINAL text, converged: false
  │
  └─ Stage 4  assemble + emit {event: done, text, score/band before+after, unconverged}
```

Scoring is a **local CPU call, not an LLM call** — gating is cheap.

### 4.2 Readability module (new, `src/text_mate_backend/readability/`)

Language-specific data is separated from language-agnostic mechanics, and everything is
typed behind one Protocol.

```
readability/
  __init__.py          public API: detect_language, get_analyzer, ReadabilityAnalyzer
  types.py             LanguageCode, ReadabilityBand, ReadabilityScore, ScaleInfo,
                       BandConfig, ReadabilityAnalyzer (Protocol)
  detection.py         fast-langdetect wrapper → LanguageCode | None
  registry.py          LanguageCode → ReadabilityAnalyzer; None when unsupported
  core/                ── LANGUAGE-AGNOSTIC ──
    tokenize.py        words / sentences / chars / long-words / polysyllables
                       (port of blokkli getWords, getSentences, sentenceCount …)
    formulas.py        flesch_reading_ease(coeffs), lix(), gulpease() — pure math
    bands.py           classify_band / impact_for_score from a BandConfig,
                       handling both higher_easier and higher_harder directions
  languages/           ── LANGUAGE-SPECIFIC ──
    german.py          ZIX-backed analyzer (delegates to zix), CEFR mapping, bands
    english.py         FRE coefficients, pyphen syllables, FRE→CEFR, bands
    french.py          LIX config + bands
    italian.py         Gulpease config + bands
```

The Protocol, mirroring blokkli's `ReadabilityAnalyzer`:

```python
class ReadabilityAnalyzer(Protocol):
    language: LanguageCode
    score_label: str  # "ZIX" | "CEFR" | "LIX" | "Gulpease"
    min_words: int

    def score(self, text: str) -> float | None: ...
    def band(self, score: float) -> ReadabilityBand: ...  # easy | ok | hard
    def cefr(self, score: float) -> str | None: ...  # de, en only
    def format_score(self, score: float) -> str: ...
    def agent_context(self) -> str: ...  # reference table for prompts
```

`in_target` is `band == easy`. Calibrations ported verbatim from blokkli's `SCORE_CONFIGS`
(`en` FRE easy ≥ 60 / ok ≥ 50 with the FRE→CEFR mapping; `fr` LIX easy ≤ 40 / ok ≤ 59;
`it` Gulpease easy ≥ 80 / ok ≥ 60), German from ZIX/ZH (easy ⇔ ZIX ≥ 0 ⇔ CEFR A1/A2/B1).
Blokkli's `builtin.spec.ts` becomes our test vectors so the port is provably faithful.

New dependencies: `fast-langdetect>=1.0.1`, `pyphen` (English syllables — the one thing
blokkli outsources, to the npm `syllable` package). Formulas are MIT via blokkli via
`@lunarisapp/readability`; record attribution in a `NOTICE`.

Not ported: Wiener Sachtextformel and `countSyllablesDe` — German uses ZIX, so both would
be dead code.

**German `min_words` is 6, not 5** *(corrected during implementation)*. ZIX warns that
texts of *5 words or fewer* are unreliable, so the lowest scorable length is 6; an earlier
draft said 5, taken from blokkli's WSTF config, but ZIX's own warning is the authority for
the German analyzer. It is defined once in `readability/languages/german.py` and imported
by `utils/simplify_chunker.py` and `text_mate_tools/simplify_eval/scoring.py` — do not
restate the literal anywhere else.

### 4.3 Scoring service (`services/text_analysis_service.py`)

Becomes language-aware, additively. `analyze()` keeps its current signature for
`POST /text-analysis`; extend its **response** with `language`, `score`, `score_label`
and `band`, keeping `zix_score` / `cefr_level` present (null for fr/it). Add:

```python
async def score(self, text: str, analyzer: ReadabilityAnalyzer) -> ReadabilityScore | None
async def score_many(self, texts: list[str], analyzer: ReadabilityAnalyzer) -> list[ReadabilityScore | None]
```

Requirements: wrap scoring in `try/except` → `None` + log (ZIX's >1M-char `ValueError`
currently reaches the client as a 500); skip texts below the analyzer's `min_words`
rather than scoring them; memoize by `(hash(text), language)` within a request; run
through a **bounded** thread pool — ZIX is CPU-bound spaCy + sklearn and `score_many` over
40 paragraphs would saturate the default executor. The formula-based analyzers are cheap
but go through the same path for uniformity. Use the currently-unused
`TEXT_ANALYSIS_ERROR` in `models/error_codes.py`.

**`analyze()` has three outcomes, not two** *(added during implementation)*. The endpoint
feeds the always-on CEFR badge, so it cannot simply refuse whatever `get_analyzer` will not
score — fastText rates a real fragment like `"Beilagen: Kopie Ausweis, Steuerbescheid"` at
only 0.66 confidence, and gating naively on detection would blank the badge on ordinary
short German. But it must also never invent a number. The two cases are separated with
`detect_raw_language`:

| Case | `language` | score fields |
|---|---|---|
| Detected and scorable | `de` / `en` / `fr` / `it` | populated with that metric |
| Detected confidently, unsupported | the **actual** code (`es`, `zh`, …) | all null |
| Detection inconclusive | `null` | ZIX-scored; badge preserved |

`UNSUPPORTED_LANGUAGE_MIN_CONFIDENCE = 0.7`, placed by measuring the model rather than
guessing: real German fragments score 0.66–0.99, ambiguous short English 0.55, clearly
foreign text 0.90–0.999. The costs are asymmetric — wrongly refusing to score German blanks
a badge shown on every paragraph, wrongly scoring a foreign fragment yields one bad number —
so the endpoint only gives up when detection is clearly sure.

The inconclusive branch reports `language: null` rather than `"de"`: scored *as* German is
not the same as known to be German, and `score_label` already says what produced the number.
**Never report a language the text is not in.** `TextAnalysisResult.language` is therefore
`str | None`, not `LanguageCode | None`.

This applies to `/text-analysis` only. `score()` / `score_many()` take an explicit analyzer,
so the simplify pipeline is unaffected and its unsupported-language branch (§4.1, no scoring
at all) still holds.

### 4.4 Chunking (`utils/simplify_chunker.py`, new)

Split on blank lines, preserving index and original offsets. Classify each unit as
`heading` (short line, no terminal punctuation), `list_item` or `paragraph`. Only
`paragraph` units are rewritten; the rest pass through verbatim. Units below the
analyzer's `min_words` are marked `unscorable` and passed through — do not rewrite what
cannot be verified. Reassembly joins outputs with `\n\n` in original index order; a unit's
output may itself contain `\n\n` (1-in-N-out).

**Deliberately simplify-local.** The advisor's only splitter today is `advisor.py`
`_split_into_search_units` (sentence-level, offset-preserving); the paragraph windowing both
features want is specified in `advisor_redesign.md` §4.2.3 but unbuilt. That redesign is at
**Phase 1 of 5** — the eval harness shipped, but ensembling/voting/verifier (Phase 2), rule
`kind`/`scope` (Phase 3), deterministic checkers (Phase 4) and the confidence-carrying
stream (Phase 5) are all still absent from the code. Unifying now means refactoring a moving
target. Leave a cross-reference in both files so advisor Phase 3 adopts this module.

What *is* shared: `utils/text_offsets.py` (`to_utf16_offset`), extracted when the simplify
service was found importing `AdvisorService` to reach a private static method. Offsets
crossing the Python/JavaScript indexing boundary get one implementation, used by
`ViolationRange` and `UnconvergedRange` alike.

### 4.5 Why not SEARCH/REPLACE — and no backend diffing at all

The frontend already owns diffing end to end: `diffSegments.ts` does a word-level diff
with adjacent-change merging and whitespace suppression, and `DiffViewer.vue` renders
accept/reject per hunk in both views, with `getResolvedText()` reconstructing the final
string. The backend returns the **final simplified text** and nothing more.

Blokkli's `[[[FIELD:N]]] / [[[SEARCH]]] / [[[REPLACE]]]` protocol and its
`FieldStreamParser` (9KB + spec) are therefore not ported: they reinvent a wheel that
already turns, and on a workload where nearly every sentence changes they degenerate to
full replacement anyway. This also sidesteps `replace_eszett` in `BaseAgent`, which mutates
ß→ss in outputs and breaks snippet matching — the live bug flagged in
`advisor_redesign.md` §9. With full-text output that postprocessor is harmless and in fact
desirable for German (Swiss orthography); it must be **disabled for non-German output**.

### 4.6 Fidelity gate — **removed**

This section originally specified a second gate inside the loop: a structured
`FidelityResult { complete, missing }` call per attempt, with missing facts injected into
the next attempt's prompt. The reasoning was that the readability gate alone *rewards*
information loss, since a shorter, emptier text scores better.

**It was built, measured, and removed.** The reasoning was sound a priori and wrong in
practice — see §13.1 for the evidence. Retries are driven by the readability band alone.

The concern it addressed is not dismissed, it is relocated to the prompt:
`REWRITE_COMPLETE` ("Kürze niemals Informationen") and `BASEL_STADT_HOUSE_STYLE` item 5
("Übernimm alle Fakten … exakt und unverändert") are the only safeguards, and they held on
every case measured. Fact preservation is still **measured** in the eval harness (§6), it
is simply no longer **gated** at runtime.

If a future corpus shows genuine loss, the cheap reinstatement is a deterministic check
over numbers, dates and CHF amounts — normalized on both sides, run once on the final text,
reported as a UI hint rather than triggering retries. Do not reinstate the LLM entailment
call without evidence that a regex cannot do the job.

### 4.7 Streaming contract

`POST /simplify` → `StreamingResponse`, JSON lines (as `/advisor/validate`;
`X-Accel-Buffering: no`).

```jsonc
{"event":"start","language":"de","score_label":"ZIX","scored":true,"mode":"whole",
 "units":12,"score_before":-3.8,"band_before":"hard","cefr_before":"C1"}
{"event":"progress","attempt":2,"stage":"readability","score":-1.2,
 "band":"ok","cefr":"B2","units_in_target":8}
{"event":"chunk_done","index":3,"text":"…","score_before":-4.1,"score_after":1.2,
 "cefr_before":"C1","cefr_after":"A2","attempts":2,"converged":true}   // CHUNKED only
{"event":"done","text":"…","language":"de","score_label":"ZIX","scored":true,
 "score_before":-3.8,"score_after":1.4,"band_after":"easy","cefr_after":"A2",
 "converged":true,"unconverged_units":[7,9]}
```

Rules: `chunk_done` is **final** — the UI never retracts shown text; it may arrive out of
order and is reassembled by `index`. `done` always carries the fully assembled text, so in
WHOLE mode the client can ignore everything but `progress` and `done`. When
`scored: false` (unsupported language) there is a single rewrite and no score fields.

`units`/`units_in_target`/`unconverged_units` are counted over the same population: merged,
scorable blocks (§14.2), never the raw blank-line-separated blocks a document splits into
before merging. Headings, list items and merged blocks still short of the analyzer's
`min_words` are excluded from all three — they are permanent barriers or unscorable, so
they can never appear in `units_in_target`, and counting them in `units` would make "every
unit in target" unreachable even on a fully-simplified document. Renamed from
`paragraphs`/`paragraphs_in_target`/`unconverged_paragraphs`: the old names counted raw,
unmerged blocks on `start` and merged units everywhere else (2–6× fewer on the real
corpus — a 258-block Ratschlag merges to 42 scorable units), so "42 von 258" reached a user
as if the tool had barely touched the document. Both sides of this fix must ship together
with the frontend's matching rename.

## 5. Prompt changes

### 5.1 Rule reconciliation (`utils/easy_language.py`, German only)

Audit every `RULES_ES` bullet against `bundeskanzlei.json`,
`merkblatt_behoerdenbriefe.json` and `BASEL_STADT_HOUSE_STYLE`. Remove what the advisor
contradicts (Null-Rappen, abbreviated units, and whatever else the audit finds).
Keep what `RULES_ES` is genuinely good at: sentence length, one thought per sentence,
active voice, positive phrasing, simple/common words, consistent terminology, explain
jargon, no nominalizations, hyphenate 4+ compounds.

The audit is recorded in [`simplify_rules_audit.md`](./simplify_rules_audit.md) — one row
per rule with the conflicting BS/BK rule, the verdict and the rationale — so every change is
reviewable.

**Outcome: 21 keep, 9 reword, 0 delete** *(recorded during implementation)*. Zero outright
deletions is not a sign the audit found nothing. Every contradicting bullet also covered a
topic the prompt still needs, so the contradicting **clause** was removed inside a reworded
bullet rather than the whole rule being dropped; each removed clause is listed verbatim in
§3 of the audit. Read the clause list, not the verdict counts, to see what actually changed.

Three rewords change user-visible output and are the first thing a reviewer should check:
`30%` now stays abbreviated and unspaced, full hours lose their `.00` (`14.00 Uhr` →
**`14 Uhr`**, per BK «Volle Stunden ohne Minutenangabe»), and a vague ZH gendering line is
replaced by the prescriptive BS/BK one. Currency stays «Fr.»/«Franken» — see §13.4.

(An earlier revision of this document stated the time change as `14 Uhr` → `14.00 Uhr`.
That was backwards: the Zurich original mandated `.00`, and the reconciliation removed it
to follow BK. The error was relayed to the reviewer and produced a self-contradictory
sign-off note, caught only because the implementing agent refused to invert a rule against
its own cited primary source.)

### 5.2 German style block (`utils/simplify_style.py`, new)

A single hand-curated, human-reviewed constant composed from:
- `BASEL_STADT_HOUSE_STYLE` — Anrede/Ton, geschlechtergerechte Sprache (incl. the explicit
  ban on Gendersternchen/Doppelpunkt/Binnen-I), Schweizer Rechtschreibung, Anglizismen;
- the on-topic `merkblatt_behoerdenbriefe` rules: Keine Floskeln, Kein Amtsjargon, Kurze
  einfach gebaute Sätze, Ein Gedanke pro Satz, Respektvoller Ton auf Augenhöhe;
- the surviving `RULES_ES` rules.

Deduplicated — several rules appear in two or three sources. This is blokkli's skill
`streamTemplates` seam as a Python constant. Prompt content is a systematic-error surface,
so human review is mandatory (the stance `advisor_redesign.md` takes on generated checkers).

### 5.3 Rewrite prompt (extends `CLAUDE_TEMPLATE_ES`)

Keeps the XML-tagged structure and `REWRITE_COMPLETE`. Adds:

1. **Score reference block** (blokkli's `getAgentContext`), rendered from the active
   analyzer's reference table, e.g. for German:
   > Der Text wird mit einem Verständlichkeits-Index bewertet (ZIX, −10 bis 10).
   > Ziel: Sprachniveau A2 oder B1 (ZIX ≥ 0). Aktuell: {cefr} (ZIX {score}).
2. **Per-paragraph issue list**, from attempt 2 — paragraphs still outside target, quoted
   with their score/band. This is the mechanism that makes the loop work.
3. **Retry block** mirroring `fixReadability.ts`: previous attempt, its score, missing
   escalating instructions ("höchstens 10 Wörter pro Satz",
   "teile jeden Satz mit mehr als einem Gedanken auf").
4. **Passing exemplars** — up to 2 already-in-target paragraphs from the same document
   with their scores. Lifted from blokkli's `passingFields`.
5. **CHUNKED mode only** — previous/following paragraph read-only, a one-line document
   summary, and an explicit "rewrite ONLY the target paragraph".

Temperature 0 on attempt 1, > 0 on retries (a deterministic retry reproduces the failure).
`BaseAgent._extract_model_settings` already supports per-call settings.

### 5.4 Non-German rewrite prompt (`utils/simplify_generic.py`, new)

For `en` / `fr` / `it` (and the unscored fallback) there is no authored rule set, so use a
**language-neutral simplification prompt** — blokkli's `defaultInstructions`, essentially:
break long sentences, replace complex or uncommon words with simpler alternatives, reduce
words per sentence, preserve meaning, tone and information — plus that language's score
reference block, plus an explicit "answer in the same language as the input". No house
style, no typography rules, no gendering rules: we have not authored those for these
languages and inventing them unreviewed is exactly the systematic error §5.2 guards
against. The loop and the retry feedback work identically; only the rule content differs. Document this asymmetry in the user-facing docs.

## 6. Evaluation harness (Phase 1 — ships before the pipeline)

Unlike the advisor eval, **the analyzer is itself the scorer, so readability needs no
hand-labelling** — this is cheap to build.

- **Corpus** `evals/simplify/cases/*.json`: 20–30 real public Basel-Stadt texts (bs.ch
  pages, Merkblätter, Verfügungen), spanning easy → very hard and spanning the 8,000-char
  threshold so **both modes are exercised**. `{id, source_text, language, source_score,
  source_band, notes}` plus optional hand-listed must-keep facts (an eval-time measurement
  of fact preservation, normalized on both sides; never a runtime gate — §13.1).
  **Status: 16 cases, 14 of them real** Basel-Stadt Grosser-Rat documents (Anzüge,
  Ratschläge, Berichte, Initiativen) converted through the docling service; 1 synthetic and
  1 borrowed case are retained with provenance recorded in the case files. Mean ZIX −3.61,
  13 of 16 band `hard`, 12 over the chunking threshold, largest 38,630 chars — see §13.3b.
  `source_score`/`source_band` remain optional so the harness never requires a pre-scored
  corpus.
- **The corpus is German.** The harness is language-parameterised but only German is
  measured against real data; en/fr/it correctness rests on the ported unit tests (§4.2).
  State this in the report header.
- **Runner** `src/text_mate_tools/run_simplify_eval.py`, per case and aggregate: score
  before/after (mean ± spread), band shift, CEFR shift where available, convergence rate,
  share of paragraphs reaching target, attempts-to-converge distribution, fidelity-failure
  rate, length ratio, wall-clock p50/p95, LLM call count — **split by mode**.
- **Baseline first**: run today's single-shot `PlainLanguageAgent` over the corpus and
  record the numbers. Every later phase is measured against that.
- Layout and CLI mirror `run_advisor_eval.py` / `advisor_eval/scoring.py`.

## 7. Task list

`[x]` done · `[ ]` outstanding · `[~]` blocked on a live vLLM endpoint (wiring in place,
measurement not yet run).

**Phase 0 — spec**
- [x] T0. This document, at `text-mate-backend/docs/simplify_redesign.md`.

**Phase 1 — eval harness (no pipeline changes)**
- [x] T1.1 Collect 20–30 public Basel-Stadt texts → `evals/simplify/cases/*.json`,
      spanning the 8,000-char threshold, with source score/band recorded.
- [x] T1.2 `src/text_mate_tools/simplify_eval/{models,scoring}.py` — metrics of §6.
- [x] T1.3 `src/text_mate_tools/run_simplify_eval.py` — per-case + aggregate report split
      by mode, `--runs N`.
- [~] T1.4 **Baseline the current single-shot agent.** Record numbers in the spec.

**Phase 2 — readability module + scoring foundation**
- [x] T2.1 Add deps `fast-langdetect>=1.0.1`, `pyphen`; add `NOTICE` attributing the
      ported MIT formulas (blokkli / `@lunarisapp/readability`).
- [x] T2.2 `readability/` module per §4.2: `types.py`, `core/{tokenize,formulas,bands}.py`,
      `languages/{german,english,french,italian}.py`, `registry.py`, `detection.py`.
- [x] T2.3 Port `builtin.spec.ts` expectations into `tests/test_readability_*.py` as test
      vectors, so the port is provably faithful to blokkli. Plus detection tests.
- [x] T2.4 Extend `TextAnalysisService`: `score()` / `score_many()` taking an analyzer;
      `try/except` + length guard + min-words skip + memoization + bounded thread pool;
      wire `TEXT_ANALYSIS_ERROR`. Extend the `/text-analysis` response **additively** with
      `language`, `score`, `score_label`, `band` (keep `zix_score`/`cefr_level`, null for
      fr/it) so the existing CEFR badge keeps working.
- [x] T2.5 `utils/simplify_chunker.py` — `\n\n` split, heading/list/paragraph
      classification, unscorable detection, index-preserving reassembly. Cross-reference
      `advisor.py:619` in both directions.
- [x] T2.6 Unit tests for chunker + scoring service (pure functions, no LLM). Follow
      `tests/test_advisor_resolver.py`, incl. `Service.__new__(Service)`.

**Phase 3 — prompt reconciliation**
- [x] T3.1 Audit `RULES_ES` against both rule JSONs + `BASEL_STADT_HOUSE_STYLE`; produce
      the conflict table; delete contradicting ZH rules.
- [x] T3.2 `utils/simplify_style.py` — reconciled, deduplicated German block. **Human
      review required before merge.**
- [x] T3.3 `utils/simplify_generic.py` — language-neutral prompt for en/fr/it (§5.4).
- [x] T3.4 Extend `CLAUDE_TEMPLATE_ES` with score-reference, issue-list, retry, exemplar
      and chunk-context blocks (§5.3), as composable template functions rather than one
      giant f-string. Select German vs generic rules by detected language.
- [~] T3.5 Re-run the eval on the single-shot path — isolates prompt gain from loop gain.

**Phase 4 — the loop**
- [~] T4.1 ~~`fidelity_check_agent.py` + `FidelityResult`~~ — built, measured, **removed** (§13.1).
- [ ] T4.2 Refactor `PlainLanguageAgent` into the loop's rewriter: accept text + scores +
      retry context + optional neighbour context + language; drop `check_readability_score`
      (dead); fix the "Leichte Sprache" docstring; remove from the quick-action registry;
      disable `replace_eszett` for non-German output.
- [ ] T4.3 `services/simplify_service.py` — orchestrator of §4.1. **WHOLE mode first**,
      then CHUNKED, then the unscored single-shot branch. Per-call timeouts,
      `asyncio.gather` + semaphore in CHUNKED, best-attempt resolution, assembly. Module
      constants for every knob (§9).
- [ ] T4.4 Register in `container.py` (`Singleton(SimplifyService, config=config,
      text_analysis_service=text_analysis_service)`).
- [ ] T4.5 Tests against a stubbed rewriter + stubbed scorer: convergence, non-convergence
      keeps the original, best-attempt-not-last selection, mode selection at the threshold
      boundary, unsupported-language branch.

**Phase 5 — API**
- [ ] T5.1 `routers/simplify.py` — `POST /simplify`, JSONL events (§4.7), auth, usage event
      `text.simplify` recording **detected and hinted language** so disagreement is
      measurable, cancel-on-disconnect (advisor pattern), `X-Accel-Buffering: no`.
- [ ] T5.2 Register in `app.py`; models in `models/simplify_models.py`.
- [~] T5.3 **Measure with the eval harness. Tune knobs against the numbers, not vibes.**

**Phase 6 — frontend**
- [ ] T6.1 `server/api/simplify.post.ts` — `apiHandler` + a `dummyFetcher` emitting a
      realistic JSONL sequence (every endpoint has one; `bun run dummy` must work).
- [ ] T6.2 `app/composables/useSimplify.ts` — JSONL parse + Zod validate per line, modelled
      on `useAdvisor.ts:80-200`. Fix, do not copy, its stale "SSE `data:`" comment.
- [ ] T6.3 Point the `plain_language` button (`ribbon/TransformTab.vue:92-98`,
      `useMobileActions.ts:241-251`) at the new flow; keep the label.
- [ ] T6.4 Progress UI while running (attempt, paragraphs in target / total).
- [ ] T6.5 Hand `done.text` to the **existing** `DiffViewer` via the current `diff-review`
      workspace state — no new diff code. Show before/after score in the diff header.
- [ ] T6.6 Generalize the score badge: `CefrScoreVisualization.vue` is CEFR-specific, but
      `fr`/`it` have no CEFR mapping. Render CEFR for de/en and `score_label` + band for
      fr/it; show nothing when `scored: false`.
- [ ] T6.7 Surface `unconverged_paragraphs` as a hint that those need a human look.
- [ ] T6.8 i18n keys in `i18n/locales/{de,en}.json`.

**Phase 7 — tune**
- [~] T7.1 Sweep the 8,000-char threshold, attempt cap, temperature schedule and exemplar
      count against the eval harness; record chosen values and their numbers in the spec.

## 8. Cost model

Revised after the fidelity gate was removed (§4.6): one rewrite call per unit per attempt,
nothing else.

| Input | Mode | LLM calls |
|---|---|---|
| ≤ 8,000 chars, converges on attempt 1 | WHOLE | **1** (rewrite only) |
| ≤ 8,000 chars, 3 attempts | WHOLE | 3 |
| > 8,000 chars | CHUNKED | 1 × failing paragraphs per attempt, parallel within an attempt |
| Unsupported language | — | 1 |

Scoring adds no LLM calls; language detection is sub-millisecond fasttext. The common case
now costs **exactly what today's single-shot action costs** — the loop is free when the
first attempt already converges, which §13 shows is the common case on the current corpus.

Measured, gemma-4-31B on 2×RTX 4090, `--max-num-seqs 1` (so CHUNKED serializes and these
wall-clocks are pessimistic): WHOLE p50 ≈ 4–5 s; the 8,365-char CHUNKED case ≈ 103–142 s
across 32 calls.

## 9. Configuration knobs

**Superseded by §14.5.** Current values: `simplify_chunking_threshold_chars` (10000),
`simplify_max_attempts` (2), `simplify_min_unit_words` (100);
`simplify_require_all_paragraphs` is removed — the per-unit gate is the only gate.

Historical list: `simplify_chunking_threshold_chars` (8000), `simplify_max_attempts` (3),
`simplify_require_all_paragraphs` (false), `simplify_temperature_first` (0),
`simplify_temperature_retry`, `simplify_max_parallel_llm_calls`,
`simplify_rewrite_timeout_seconds`, `simplify_max_parallel_llm_calls` (tuned against
production hardware, not this dev box — the dev server's `--max-num-seqs 1` makes any value
inert),
`simplify_exemplar_count` (2), `simplify_supported_languages` (`de,en,fr,it`),
`simplify_language_detection_min_chars`.

Gate detail: in WHOLE mode the pass condition is the **whole-text** band. Paragraphs still
below target are reported (stream, UI, eval) but do not block — a per-paragraph AND would
frequently never converge on documents containing an unavoidably dense clause. Exposed as
`simplify_require_all_paragraphs`, default `false`.

## 10. Language support

| Language | Metric | CEFR? | Rewrite rules |
|---|---|---|---|
| `de` | ZIX (trained model) | yes, native | Full: reconciled `RULES_ES` + Basel-Stadt style block |
| `en` | Flesch Reading Ease | yes, mapped | Generic language-neutral prompt |
| `fr` | LIX | no | Generic language-neutral prompt |
| `it` | Gulpease | no | Generic language-neutral prompt |
| other | — (not scored) | no | Generic prompt, single shot, no loop |

The asymmetry is deliberate and must be documented for users: **German gets a
Basel-Stadt-specific style, the others get generic simplification.** Measuring in four
languages is cheap; authoring and reviewing administrative style guides in four languages
is not, and unreviewed style rules are a systematic-error surface.

Note the bands are each analyzer's own calibration, so "easy" is not numerically identical
across languages — blokkli's English table marks B2 as the target while German targets
A2/B1. That is inherent to using different, separately-calibrated metrics; the eval only
compares like with like.

## 11. Open questions / risks

- **Detection on short texts.** fasttext is unreliable below a few sentences. Hence
  `simplify_language_detection_min_chars`: below it, fall back to the client's hint, and
  below that to German. Verify the threshold empirically.
- **ZIX throughput.** spaCy + sklearn per paragraph per attempt. If profiling shows it
  dominating, options are a persistent process pool or scoring only changed paragraphs
  (memoization already covers the second). The formula-based analyzers are cheap.
- **ZIX at paragraph length.** ZIX was trained on documents; per-paragraph scores will be
  noisier. In WHOLE mode this only affects diagnostics, so the risk is contained — but in
  CHUNKED mode it is the gate. The eval must confirm per-paragraph gating correlates with
  whole-text improvement; if not, CHUNKED mode should gate on a rolling window.
- **Threshold is a guess until measured.** 8,000 chars comes from output-length reasoning
  and ZH's 10,000-char input cap, not from our data. T7.1 exists to correct it.
- **English syllables via pyphen** are hyphenation-based, not phonetic; FRE is sensitive to
  them, so English scores are the least trustworthy of the four. The ported test vectors
  bound the error.
- **The chunking threshold is now the biggest untuned knob.** 12 of 16 real documents
  exceed 8,000 chars, so CHUNKED is the normal path rather than the exception the design
  assumed (§13.3b). With `max_model_len` at 198,944 the reasoning that produced 8,000 no
  longer applies. T7.1 must re-derive it against wall-clock and quality on the real corpus.
- **CHUNKED latency is measured and accepted, not solved** (§13.6): p95 612 s, worst case
  738 s. Accepted on the basis that the progress UI makes it legible; `--max-num-seqs 1` is
  the cause and raising it is the known lever if real use disagrees.
- **Per-paragraph convergence does not imply document convergence** (§13.6). A case where
  all 83 paragraphs reached target still scored below it as an assembled document. Any UI or
  metric that assumes the two agree will mislead.
- **Length ratio is a crude information-loss proxy** — a rewrite can be longer and still
  drop a deadline. The hand-listed must-keep facts are the real measure.
- **`RULES_LS` stays dead.** Single-target decision. The architecture would support Leichte
  Sprache by swapping the rule set and target band, but that is explicitly not v1.

## 12. Verification

- `mise test` / `make test` — unit tests for the readability module (against blokkli's
  ported vectors), detection, chunker, scoring service and loop logic. All run without an
  LLM.
- `uv run python -m text_mate_tools.run_simplify_eval --runs 3` — the primary signal.
  Success = convergence rate and mean band/CEFR shift materially above the Phase 1
  baseline, p95 wall-clock acceptable, WHOLE mode used for
  the large majority of cases.
- Manual: `mise dev` + `bun run dev`. Paste a hard German Behörden text → progress streams,
  diff opens with before/after CEFR, accept/reject works, `getResolvedText()` returns the
  expected text. Repeat with a >8,000-char document (CHUNKED), an English text (FRE→CEFR,
  generic rules), a French text (LIX, no CEFR badge) and a Spanish text (single shot, no
  score).
- `bun run dummy` — frontend works offline against the dummy fetcher.
- Regression: `POST /text-analysis` still returns `zix_score`/`cefr_level` for German;
  other quick actions unaffected.

## 13. Measured results and design reversals

First measurements against a live model: gemma-4-31B-it-NVFP4 on vLLM v0.26.0,
tensor-parallel across 2×RTX 4090 (`max_model_len` 198,944), `--max-num-seqs 1`.

**Read every number below as directional.** The corpus is 4 cases, one of them synthetic
(§6). Nothing here is strong enough to settle a tuning question; it is strong enough to
overturn a design assumption, which is what it did twice.

### 13.1 The fidelity gate was removed on evidence

The gate was specified from an a priori argument (§4.6: the readability gate rewards
information loss). Measurement did not support it.

Every must-keep fact in the 8,365-char Merkblatt case survived the rewrite:

| must-keep fact | in output as | lost? |
|---|---|---|
| `dreissig Tagen` | `30 Tagen` | no |
| `sechzig Tage` | `60 Tage` | no |
| `vierzehn Tagen` | `14 Tagen` | no |
| `zwanzig Tagen` | `20 Tagen` | no |
| `drei Monate` | verbatim | no |
| `40.50 Franken` | `Fr. 40.50` | no |

6 of 6 preserved. Every apparent loss was the spelled-out-number → digit conversion that
the Bundeskanzlei Fristen rule *requires* — the prompt working as designed, scored as
failure by an exact-substring check.

Three findings together:

1. **No information loss** in the only realistic document available.
2. **The gate's firings were false positives**, on transformations we mandate.
3. **The gate was flaky** — `fidelity_failures=0` on one run and `1.00` on another, same
   case, same content. Worse than a consistent false positive, because it cannot be
   reasoned about.
4. **It cost 100% extra LLM calls** in WHOLE mode (1 → 2) for no measured benefit.

Removed entirely, no replacement (§4.6 records the cheap reinstatement path if a real
corpus ever shows loss). Fact preservation is still measured in the harness, with
normalization on both sides so mandated reformatting stops registering as loss.

### 13.2 `converged` was mode-dependent and misleading

It meant "whole-text band reached" in WHOLE and "every unit in target" in CHUNKED. The
Merkblatt case therefore reported `convergence rate 0.00` beside `in-target rate 1.00`:
the assembled text *was* easy (ZIX −3.86 → 1.41) while one paragraph never got there.
T7.1 is meant to tune against convergence rate, so a metric meaning two things was a trap.
Now mode-independent — "the assembled text reached the target band" — with per-paragraph
shortfall reported via `unconverged_paragraphs`.

### 13.3 The loop earns its keep — after the corpus and the metric were fixed

**This section previously recorded the opposite conclusion.** It is kept as a correction,
because how the error happened matters more than the number.

The first A/B, on the 4-case corpus and before `converged` was made mode-independent,
showed single-shot and the full loop scoring identically (`in_target 1.00` both, loop
18–38% slower) and this document concluded the loop "buys nothing measurable". That was an
artifact of reading the broken metric described in §13.2. Once `converged` meant the same
thing in both modes, the difference appeared:

| WHOLE | single-shot | full loop |
|---|---|---|
| convergence rate | 0.67 | **1.00** |
| in-target rate | 0.67 | **1.00** |
| wall-clock p50 | 4.2 s | 6.2 s |

One case in three fails a single pass and reaches target on retry. Across the whole corpus
the loop cost 3 extra LLM calls (16 → 19) for convergence 0.75 → 1.00.

Two lessons, both cheap to state and expensive to relearn:

1. **A metric that means two things will manufacture a false conclusion**, and it will look
   like data. The fix in §13.2 was filed as a reporting tidy-up; it changed a design verdict.
2. **A corpus that cannot discriminate reads exactly like a feature that does not work.**
   The original 4 cases converged on the first attempt no matter the configuration, so every
   setting scored 1.00 and the loop looked like pure overhead.

### 13.3b The corpus is now real, and it falsifies a design assumption

16 cases, 14 of them real Basel-Stadt Grosser-Rat documents (Anzüge, Ratschläge, Berichte,
Initiativen), converted through the docling service the backend already wraps.

| | old | new |
|---|---|---|
| cases | 4 (1 synthetic) | 16 (1 synthetic) |
| mean ZIX | −1.69 | **−3.61** |
| bands | 1 easy, 2 ok, 1 hard | 1 easy, 2 ok, **13 hard** |
| ZIX range | — | −5.70 … 0.28 |
| largest | 8,365 chars | **38,630 chars** |
| over the 8,000-char threshold | 1 of 4 | **12 of 16** |

**Chunking is not the exception.** §4.1 asserts "chunking only above 8,000 chars — the
exception, not the rule". On real parliamentary text **75% of documents exceed it**, so
CHUNKED is the normal path, not the fallback. The 8,000 figure was derived from
output-generation length when we assumed a small context window; `max_model_len` is now
198,944, so the constraint that produced the number no longer binds. T7.1 must re-derive
the threshold rather than inherit it — and should weigh that CHUNKED costs context (§4.1)
against WHOLE costing a single very long generation on a 38,000-char Ratschlag.

### 13.4 Prompt compliance gap — and a correction the review reversed

The rewrite produced `Fr. 40.50`. This was recorded here as a compliance miss on the
grounds that `Fr.` is an abbreviation the rules tell us to avoid, and the prompt was
changed to mandate `CHF 40.50`.

**That was wrong, and the model's original output was correct.** Human review established
actual Basel-Stadt practice: **«Franken» spelled out in Fliesstext, «Fr.» as the
abbreviation with a precise figure** — which is also what the Bundeskanzlei's own examples
use (`Fr. 327.65`). The CHF mandate has been reverted.

The reasoning that produced the error is worth keeping, because it will recur: BS had **no
currency rule in the repo**, BK permits `Fr., CHF, EUR` and rules only on placement, so
narrowing to `CHF` looked like a safe house-style choice supported by the abbreviation rule.
Every step was defensible from the material available; the material was simply incomplete.
**Absence of a rule in `house_style.py` is not absence of a convention** — it means the
convention is not encoded, and a human who knows the house style must be asked.

The genuinely transferable finding stands and was the real root cause: the money bullet
stated its rule but *illustrated* it with a contradicting example, and the model copied the
example. Rules whose examples disagree with their text will be followed by the example.

### 13.5 Process failure worth recording

§6 says "baseline first — every later phase is measured against that". That did not happen.
T1.4 was blocked on having no GPU, Phase 4 ran anyway, and it retired the `plain_language`
quick action — the very thing T1.4 was supposed to measure. When a GPU appeared, the
baseline path returned a 400 by design.

The production-today baseline was therefore never captured. It is recoverable from git if
needed; the decision was not to. The lesson is the ordering constraint in an eval-first
plan is a real dependency, not a preference: **do not let a phase retire the thing an
earlier, blocked phase exists to measure.** The same trap is live in
`advisor_redesign.md`, whose Phase 1 is also a baseline.

### 13.6 First measurement on the real corpus

16 cases, 14 real Grosser-Rat documents. gemma-4-31B on 2×RTX 4090, `--max-num-seqs 1`,
both configurations run **sequentially** so neither contends for the GPU.

| | single-shot | full loop |
|---|---|---|
| WHOLE convergence (4 cases) | 0.50 | **1.00** |
| CHUNKED convergence (12 cases) | 0.83 | **0.92** |
| WHOLE p50 / p95 | 5.2 s / 40.9 s | 7.2 s / 74.6 s |
| CHUNKED p50 / p95 | 218 s / 410 s | 324 s / 612 s |
| LLM calls, corpus total | 527 | 784 |
| errors | 0 | 0 |

**The loop earns its keep on real material.** 15 of 16 cases converge; every case moves from
band `hard` to `easy` except the hardest. Typical gain ≈ **+5 ZIX**, i.e. C1/C2 → A2/B1:

    ratschlag-otterbach          28,621 chars   −4.78 → +0.12   easy
    bericht-prostitution         38,630 chars   −3.41 → +1.35   easy
    motion-menschenhandel        26,115 chars   −5.08 → +1.08   easy
    initiative-erben-fuers-wohnen 27,243 chars  −5.73 → −0.16   ok   ← the one miss

#### A whole-document score is not the mean of its paragraphs

`initiative-erben-fuers-wohnen` reports `converged: false` while **all 83 of its paragraphs
individually reached target**. The assembled text scores −0.16 — band `ok`, a hair under the
0 threshold. This is a real property of ZIX, which measures sentence length and vocabulary
across the whole text, not an averaging of parts.

Two consequences worth designing around:

1. Per-paragraph convergence in CHUNKED mode **does not imply** document convergence. §11
   flagged the risk that per-paragraph ZIX is noisy; this is the same coin's other face.
2. The user can be told "did not reach the target level" with **nothing to point at**,
   because `unconverged_paragraphs` is legitimately empty. The UI must handle that state —
   it is not a contradiction and not a bug.

#### Latency: measured, understood, accepted

CHUNKED p95 is 612 s (worst case 738 s for a 28,621-char Ratschlag). The cause is
`--max-num-seqs 1`: §8 assumes CHUNKED paragraph rewrites overlap, and with a single serving
slot they serialize — otterbach issued 146 calls back to back.

**Decision: accept it and leave the GPU config alone.** The streaming contract (§4.7) and the
progress UI (T6.4) exist precisely so a multi-minute run is legible rather than a frozen
spinner. Record two caveats with the numbers:

- Every wall-clock figure in this document is the **pessimistic serialized case**, not the
  design's intended behaviour. Do not cite them as the cost of the architecture.
- Raising `--max-num-seqs` is the known lever if the latency proves unacceptable in use.
  KV cache is 11.11 GiB / 198,944 tokens, so there is headroom; the value is 1 only because
  it was tuned for the earlier single-GPU layout, which no longer applies.

#### Known reporting gap

`unconverged_paragraphs` is plumbed through `SimplifyOutput` and the runner's adapter, but
`CaseRunResult` does not carry it, so it reads `None` in every eval record. The eval
therefore cannot yet answer how long that list gets on real documents — which matters,
because it is what T6.7 shows the user: a hint naming five paragraphs of a 153-paragraph
Bericht is a very different UX from one naming a single paragraph.

## 14. Revised loop: per-unit gate, one retry, one user-facing number

Supersedes the gate and retry design in §4.1/§4.4 and the mode split. Decided after the
first real-corpus measurement (§13.6); **not yet implemented**.

### 14.1 Why the gate moves to the paragraph

The old WHOLE-mode gate was the whole-text band, with per-paragraph scores used only as
prompt signal. That is the wrong user-facing criterion: a citizen who hits one dense
paragraph in an otherwise easy Ratschlag has hit a wall, and a document average is exactly
the statistic that hides it. §13.6 showed the two verdicts genuinely disagree —
`initiative-erben-fuers-wohnen` had all 83 paragraphs in target while the assembled document
scored −0.16 (`ok`).

### 14.2 Units: merge to ≥100 words, respect structure

Gating per paragraph is only sound if a paragraph can be measured. Measured deviation of ZIX
against a known-good score, by text length (68 paragraphs ≥90 words, prefix vs full — an
upper bound, since prefixes also differ in content):

| prefix words | mean \|ZIX(prefix) − ZIX(full)\| | p90 |
|---|---|---|
| 10 | 3.17 | 6.50 |
| 20 | 2.24 | 4.30 |
| 30 | 1.81 | 4.20 |
| 40 | 1.42 | 3.80 |
| 60 | 1.01 | 2.60 |
| 80 | 0.72 | 1.50 |

**Bands are 2 ZIX wide.** At the corpus median paragraph length (35 words) the error is ~1.8
— nearly a full band, so gating per raw paragraph would retry on noise.

Therefore: **merge paragraphs forward until a unit has ≥100 words.** Headings and list items
(`classify_unit`) are **barriers** — never merged into or across. Effect on the real corpus:

| min_words | units | median words | 153-paragraph Bericht |
|---|---|---|---|
| 6 (old) | 560 | 35 | 56 units |
| **100** | **280** | **105** | **38 units** |
| 150 | 244 | 106 | 33 units |

100 gives ~2:1 merging — two typical paragraphs per unit — while landing where measurement
error is well under half a band. A merged unit that fails is **retried as the merged block**,
not split back apart.

### 14.3 Flow: one pass, one retry, in parallel

```
pass 1   whole document in one call        (≤ simplify_chunking_threshold_chars)
         else unit-wise                    (a 38,630-char Bericht is ~12k output tokens
                                            in one generation — context is not the limit,
                                            sustained generation quality is)
   │
   ├─ score every unit
   │
   ├─ all units in target → done
   │
   └─ failing units → exactly ONE retry each, fired CONCURRENTLY
         → merge retried units back into the pass-1 result
```

`simplify_max_attempts` becomes 2 by construction. Cost is `1 + F` calls (F = failing units)
instead of up to 3 whole-document passes.

**Retries are parallel.** Production serves with `--max-num-seqs 256`; the dev box in §13.6
runs `1`, which is why every wall-clock figure recorded there is the serialized worst case.
Bound concurrency with `simplify_max_parallel_llm_calls`, do not fire unbounded.

### 14.4 What the user sees: exactly one number

The user is shown **the whole-document readability only** — the same figure as the text-stats
panel. Per-unit levels are never surfaced: two readability numbers on screen invite the user
to reconcile them, and §13.6 proves they can legitimately disagree.

The shortfall hint (T6.7) **stays, without levels**: name the passages that could not be
simplified further so the user can check them by hand, but attach no second score. On a hard
Ratschlag those blocks are exactly what a Behörde must review before publishing.

Internally `converged` is per-unit. It drives the hint, not the badge.

### 14.5 Knob changes

`simplify_min_unit_words` **100** (new — merge target), `simplify_max_attempts` **2**,
`simplify_chunking_threshold_chars` **10000** (raised from 8000, §13.6).
`simplify_require_all_paragraphs` disappears: the per-unit gate is now the only gate.

### 14.6 Measured: §14 against the previous design

Same 16-case corpus, same hardware, both run sequentially.

| | §4 loop (3 whole-text attempts) | **§14 loop (1 pass + 1 retry)** |
|---|---|---|
| documents reaching band `easy` | 15/16 | **12/16** |
| LLM calls, corpus total | 784 | **302** (−61%) |
| total wall clock | 69.0 min | **45.7 min** (−34%) |
| CHUNKED p50 / p95 | 324 s / 612 s | **275 s / 412 s** |
| units per document (Bericht) | 56 raw paragraphs | **38 merged units** |

**Decision: keep `max_attempts = 2`.** The three-document gap is not worth 482 extra LLM
calls, because the four documents that miss are all within measurement error of the line:

    bs-brief-unpersoenlich        −1.48 → −0.11  (ok)
    bs-gr-anzug-arbeit-auf-abruf  −4.77 → −0.17  (ok)
    initiative-erben-fuers-wohnen −5.73 → −0.12  (ok)
    ratschlag-otterbach           −4.78 → −0.03  (ok)

Every one sits between −0.03 and −0.17 against a threshold of 0, while §14.2 measures ZIX
error at unit length at roughly **1.0** — the gap is five to thirty times smaller than the
uncertainty of the instrument declaring it a failure. Treating these as quality regressions
would be over-reading the score. Note also that each is a large real improvement
(−4.78 → −0.03 is nearly five ZIX points, C2 → high B2).

The implementation reproduces the design analysis: 282 paragraph units at
`min_unit_words=100`, median 102 words, the 153-paragraph Bericht reduced to 38 units —
against §14.2's predicted ~280 / ~105 / 38.

#### `converged` is now a poor headline — the third metric to mislead here

The eval reported `convergence_rate 0.00` for CHUNKED and 4/16 overall, while **12 of those
same 16 documents reached band `easy`**. Both are true: `converged` is per-unit (§14.4), so
a document in target with one short unit inside it counts as unconverged. As a leading
number it says "total failure" about a mostly successful run.

This is the third time a metric's name outran its meaning in this project — §13.2 (mode-
dependent `converged`) and §13.3 (which reversed a design verdict) were the others. The
pattern is worth naming: **a metric whose definition is one sentence longer than its name
will be read by its name.** The eval report now leads with *documents in target* — what a
user experiences — and reports *units in target* separately, under a name that cannot be
mistaken for it.

### 14.7 Corpus: must-keep facts reviewed, seven corrected

All 16 cases now carry `must_keep_facts_reviewed: true`. Human review caught the ones a
machine could not, and corpus validation then caught seven facts that were transcribed
close-but-wrong — each present in the document, none an exact substring of `source_text`:

| recorded | actually in the source |
|---|---|
| `FD/P225295` (+ `P225472`, `P225573`, `P225584`) | only the first number carries the `FD/` prefix |
| `JSD/211051` | `JSD/P211051` |
| `BVD/260741` | `BVD/P260741` |
| `Kersten Wenk` | `Kerstin Wenk` |

Worth noting the failure mode rather than just the fix: **a must-keep fact that is not a
substring of its own source can never be preserved**, so those three documents would have
reported permanent phantom losses — the same class of false signal that got the fidelity
gate removed (§13.1). The `validate_cases` substring check is what caught it, which is the
argument for keeping validation strict rather than normalizing it away.

### 14.8 The scorer's own dependency was mispinned

`pyproject.toml` carried `scikit-learn>=1.8,<1.9` under the comment *"Pin scikit-learn to
match the version zix's bundled pickles were built with"* — while `zix/data/*.pkl` carry the
version string **1.9.0**. The pin excluded exactly the version it existed to match, so every
ZIX load raised sklearn's `InconsistentVersionWarning` ("may lead to breaking code or
invalid results").

Root cause: **`zix` is a git dependency with no pinned ref**, so `uv sync` takes whatever is
on main. Upstream rebuilt its pickles with 1.9.0 and the pin silently went stale. Re-check
this whenever `zix` moves — or pin the ref.

Corrected to `>=1.9,<2`. **All 16 corpus scores are bit-identical before and after**, so
every measurement in §13 and §14 stands as recorded. That was the likely outcome —
`StandardScaler` and `Ridge` are parameter containers, so a cross-minor unpickle computes
the same arithmetic — but "likely" is not "verified", and the numbers here carry design
decisions.

Worth noting how it surfaced: not from a failing test, but from two lines of pytest warning
output that had been printing all along under a passing suite.

### 14.9 Four UI defects: what the stream said vs. what the user saw

Reported from the running app on a 26,019-char Grosser-Rat document. The loop itself was
correct in all four; every defect was in what the client was told, or what it did with it.

**1. The progress panel froze on the wrong label.** `SimplifyProgressEvent` was emitted once
per *round*, after every unit in that round had come back. On a 23-unit document that is the
entire wall-clock. Until then the client held its initial state — attempt 1, `stage`
undefined, 0 in target — and `SimplifyProgress.vue` falls back to the readability label when
`stage` is absent, so the panel read *"Lesbarkeit wird gemessen…"* with a spinner and a
frozen `0 von 23` for minutes while the model was in fact rewriting. A working run and a hung
one were indistinguishable.

Fixed by making the phase explicit: `SimplifyStage` gains `"rewriting"`, announced *before*
the call that spends the time, and CHUNKED mode now emits one progress event **per unit that
lands** rather than one per round. Failures and misses emit too, so a round where nothing
converges still looks alive.

**2. The streaming preview was assembled in the wrong coordinate space.** `useSimplify`
built a running preview by splicing each `chunk_done` into `source.split("\n\n")` at the
event's `index`. But `index` addresses **merged** units (§14.2) while the split is over raw
blank-line blocks — 23 against 40-plus on this document. Every finished unit landed at an
unrelated position, so the preview showed text that had never existed. `useWorkspace` then
entered the Diff Review on the *first* one, mid-run: the user was pulled out of the editor,
watched the mis-placed preview grow, and had it replaced again at `done`. That is the
"flicker" in the report.

Fixed by deleting the preview. A client cannot place a unit without its source span, and the
span is only known at `done` — where the authoritative assembly already is. The Diff Review
is entered exactly once, when the run is over; the (now live) progress panel is what reports
the run in flight.

**3. A failed run was reported as a success.** With vLLM down every rewrite returned `None`,
so `replacements` stayed empty and `done.text` came back byte-identical to the source. The
DiffViewer has no way to tell that from a genuine no-op and rendered *"TextMate hat nichts zu
ändern gefunden."* — the most misleading thing available, since the text was never looked at.

Fixed by putting the distinction on the wire: `_rewrite` is the single funnel for "produced
nothing usable" (timeout, exception, empty generation alike), so it counts, and
`rewrite_failures` rides on `done` and `SimplifyOutcome`. A non-zero count swaps the
reassuring message for an explicit failure notice.

**4. The unconverged marks had no way out.** `useSimplifyRanges.clear()` existed and was
exported, but nothing in the UI reached it: the only way to lose a mark was to edit its text
until the range collapsed. 23 amber highlights, no dismiss. `SimplifyRangeNav` now carries a
close button.

**Verified** by driving the real app (Playwright, `channel: "chromium"`): against the dummy
backend for 1, 2 and 4, and against the live backend with vLLM down for 3 — the exact
condition in the report. Regression cover: 4 backend tests for the progress sequence, 4 for
the failure count, 6 frontend tests on the stream folding. The two that pin defect 2 were
confirmed to fail against the old code before being kept.

**The pattern, again.** Not one of these came from a failing test, and all four were live in
a suite that passed. Three are the same shape as §13.2 and §14.7: *a number or a label that
does not mean what its name says*. `chunk_done.index` reads like a paragraph index and is
not; `stage` defaulting to `readability` reads like a measurement and was not; an unchanged
`text` reads like "no changes needed" and was not. The frontend contract now names the
merged-unit space explicitly wherever an index or a count crosses it.

### 14.10 Failing fast when the model is unreachable

Follow-up to §14.9: with the model down, the run took **two minutes and 47 seconds** to
arrive at "nothing changed". Measured on `bs-gr-anfrage-steuervermeidung` (22,870 chars),
model pointed at a closed port:

| | time to fail | LLM calls |
|---|---|---|
| Before | **167.4 s** | 62, all failed, reported as "nothing to change" |
| Abort only (published `dcc-backend-common`) | **12.3 s** | ~4 |
| Abort + the retry fixes below | **2.0 s** | ~4 |

Two independent causes, at two layers.

**One unreachable call took 10.4 s, not milliseconds.** `dcc-backend-common`'s
`BaseAgent` wraps its httpx client in an `AsyncTenacityTransport`, and then hands that
client to `OpenAIProvider` — which builds an `AsyncOpenAI` whose own `max_retries`
defaults to 2. The two layers **multiply**: `llm_max_retries=2` means 3 transport
attempts × 3 SDK attempts = 9 requests, with exponential backoff between. That silently
falsifies the library's own test, `test_retry_stop_is_max_retries_plus_one`. Measured
against a closed port: 10.3 s at `llm_max_retries=2`, 4.3 s at 1, 1.4 s at 0 — the last
being the SDK's retries alone, with tenacity switched off entirely.

Fixed in `/home/yanick/code/backend-common` by constructing the `AsyncOpenAI` client
explicitly with `max_retries=0`: retrying is tenacity's job, since it is the layer that
honours `Retry-After`.

**A refused connection was being retried at all.** The predicate was
`httpx.HTTPStatusError | httpx.TransportError`, and `TransportError` covers
`ConnectError`. Nothing is listening; backoff cannot change that. Narrowed to
`TransportError` *minus* `ConnectError` — subtracting the one case rather than
enumerating the ones worth keeping, because the family is broad and everything else in
it is a genuine transient. A first attempt at this enumerated the types instead and
silently dropped `RemoteProtocolError`, i.e. the dropped-keepalive case that pooled
connections to a local model hit most often; the test now pins all four.
`ConnectTimeout` is deliberately unaffected — it derives from `TimeoutException`, not
`ConnectError`, so a slowly-accepted connection is still retried.

**The run kept going after the first one.** Even at zero cost per call, a doomed run
worked through every unit and then did it again for the retry round — 62 calls — before
returning the unchanged text. `ModelUnavailableError` now ends the run at the first
transport-level failure. The distinction it draws is the point: *the model answered
badly* is a property of one unit (count it, keep the original, carry on), while *the
model cannot be reached* is a property of the run.

Classification reads the **cause chain**, not the exception type: pydantic-ai wraps the
failure twice (`ModelAPIError` → `openai.APIConnectionError` → `httpx.ConnectError`), and
`__context__` is followed as well as `__cause__` because a re-raise inside `except` links
via the former.

Calls already dispatched cannot be recalled, and the semaphore admits the next unit the
moment one releases it, so a wave or two is still paid for — the test asserts the part
that actually costs the minutes: that units which never started are abandoned, and that
no unit is ever retried once the model is known to be unreachable.

**The frontend no longer opens a Diff Review for it.** A run that failed *and* returned
the text unchanged has nothing to review; it raises a toast and leaves the user in the
editor. Partial failures still open the review — some units were rewritten and deserve a
decision — with the toast as the warning.

> `dcc-backend-common` is a published dependency (`>=0.1.16`). Until a release carrying
> these two fixes, textmate gets the 12.3 s column, not the 2.0 s one.

### 14.11 The progress count travelled with the bar

Reported as "very weird": the `n von y Textabschnitten` line slid left-to-right as the bar
filled. It was in `UProgress`'s `status` slot, whose container is **sized to the
percentage** — Nuxt UI's intent is a label that tracks the bar's head. Measured at 0 %,
the text sat 891 px from the panel's right edge; pinned, it sits at the padding, 13 px,
and stays there. Moved out of the slot to its own right-aligned row.

Worth recording how nearly this one was mis-verified: the first check asserted only that
the offset was *stable across samples*, which a single sample satisfies trivially — it
passed against the broken layout. Stability was never the property; sitting at the right
edge was.

## 15. Measured: the redesign against what shipped on `main`

Every number in §13 and §14 compares one configuration of the new pipeline against another.
None of them answers the question a reader outside the project asks first: **what did all
of this buy over the single prompt that was already in production?** This section answers
it, on 2026-08-15, on the 16-case Basel-Stadt corpus.

### 15.1 What the baseline is

`--simplifier main_single_shot` (`simplify_eval/main_baseline.py`) — not
`simplify_single_shot`, which is the *new* pipeline with the retry switched off and is an
ablation, not a baseline. `main_single_shot` reproduces the `main` path end to end: one LLM
call for the whole document however long it is, no chunking, no readability measurement at
any point, `main`'s prompt verbatim at commit `5a5079a` (the Zurich rule formulations, before
the Bundeskanzlei reconciliation of §5.1), inside `QuickActionBaseAgent`'s instruction
envelope. Its prompt constants are **copied, not imported**: a baseline that follows the
current branch's edits is not a baseline. `main`'s decorative `check_readability_score`
tool is not reproduced — nothing on `main` acted on its output, and reproducing it would
make the call count depend on whether the vLLM build advertises tool calling.

Both runs: one run per case, same corpus, same hardware, same model
(`Gemma/Gemma-4-31B`, NVFP4), back to back, scored by the same `GermanZixScorer`.

### 15.2 The readability numbers say the two are equal

|  | `main` single-shot | §14 loop |
|---|---|---|
| ZIX after, all modes | **+0.84** ± 0.66 | **+0.81** ± 0.79 |
| ZIX shift | +4.45 ± 1.35 | +4.42 ± 1.34 |
| CEFR levels gained | 2.12 | 2.00 |
| documents reaching band `easy` | **14/16** | **12/16** |
| paragraphs in target | 0.04 → 0.56 | 0.04 → 0.67 |
| LLM calls, corpus total | **16** | **302** |
| wall clock, corpus total | **19.2 min** | 49.7 min |

Read alone, this table says the redesign cost 19× the calls and 2.6× the wall clock to lose
two documents. That reading is wrong, and the next table is why.

### 15.3 The baseline reaches the band by deleting the document

|  | `main` single-shot | §14 loop |
|---|---|---|
| length ratio, all modes | 0.72 | **1.04** |
| length ratio, CHUNKED (9 long docs) | **0.50** | **1.11** |
| must-keep facts lost, all modes | **48**, in 12/16 runs | **19**, in 9/16 runs |
| must-keep facts lost, CHUNKED | **44**, in 9/9 runs | **15**, in 6/9 runs |

`bs-gr-bericht-prostitution`: 38'630 → 12'644 characters, 8 facts gone. `erben-fuers-wohnen`:
27'243 → 8'603, 9 facts gone. `motion-menschenhandel`: 26'115 → 12'785, 9 facts gone. What
disappears is not padding — it is Geschäftsnummern (`18.1256.01`, `FD/P260515`), enactment
dates, `§`/`Art.` citations, budget position codes, and in one case a co-signing Grossrat.

This is the mechanism the ZIX column cannot see, and it is exactly the failure §4.4 predicted
in the abstract: **ZIX scores the text you hand it, so deleting the hard two-thirds of a
document is a valid strategy for maximising it.** The loop's per-unit gate forecloses that
strategy structurally — a unit that is gone cannot score `easy` — which is why the loop is
*behind* on the headline metric and ahead on every fidelity metric. A single-number eval
would have ranked these two systems the wrong way round.

The prompt is identical on this point in both systems (`REWRITE_COMPLETE`: "Kürze niemals
Informationen"), so this is not a prompt-quality difference. It is what a single call does
when asked to rewrite 38'000 characters, whatever the instruction says.

> **The fact counts moved during this run.** Both systems' totals were first reported as 59
> and 27, of which 19 (11 + 8) were `Mio.` → `Millionen` — a conversion `RULES_ES` *requires*
> ("Vermeide Abkürzungen grundsätzlich"), scored as data loss by the exact-substring test.
> `simplify_eval/normalize.py` now expands the abbreviations the rules mandate, and the
> numbers above are the re-scored ones. The direction of the finding is unchanged; the false
> positives were roughly symmetric.

### 15.4 A house-style regression, measured

Hyphenated compounds (`Betriebs-Bewilligung`, `Arbeit-Nehmende`, `Regierungs-Rat`), the
Leichte-Sprache A1 convention, in each system's output over the whole corpus:

| `main` single-shot | §14 loop |
|---|---|
| **5.41** per 1000 chars (636 total) | **1.01** per 1000 chars (255 total) |

`main`'s `RULES_ES` carries the Zurich bullet "Wenn du vier oder mehr Wörter zusammensetzt,
setzt du Bindestriche"; the reconciled rule set of §5.1 does not push it the same way. On
`bs-merkblatt-betriebsbewilligung` the baseline produced 52 instances in one Merkblatt.

### 15.5 Four blind judges, 64 verdicts

ZIX cannot answer "would a Basel-Stadt department send this out". Four LLM judges read the
two output sets blind — `evals/simplify/blind_judge_protocol.md` for the instructions,
`simplify_eval/build_blind_pairs.py` for the tree, which randomises A/B **per case** and
**balanced** 8/8, with the key written outside the tree. The roles are chosen to conflict:

| judge | `main` | loop | tie |
|---|---|---|---|
| Betroffene:r Bürger:in | 5 | **7** | 4 |
| Verwaltungsjurist:in | 3 | **9** | 4 |
| Fachperson Einfache Sprache | 1 | **11** | 4 |
| Kommunikation Staatskanzlei | 2 | **12** | 2 |
| **total** | **11** | **39** | **14** |

All four prefer the loop, and the *spread* is the informative part: the citizen, who only
asks "can I act on this", finds the two nearly equal (7–5) — the baseline's deletions mostly
remove things a citizen never needed. The jurist and the Staatskanzlei, who need the
citation and the register, split 9–3 and 12–2. **The value of the redesign is concentrated
exactly where an administration is liable**, and a reader-comprehension eval alone would
have measured almost none of it.

Judges named defects on both sides. Two of the loop's, verified in the output rather than
taken on the judge's word: it renders "Anzug" as "Klage" four times in
`bs-gr-bericht-prostitution` (a parliamentary motion is not a lawsuit), and it drops
co-signer "Tobias Christ" from the nine-name list in `bs-gr-anzug-feuerwerks-littering` —
both present and correct in the baseline's output. The loop is better, not good.

### 15.6 Caveats

* **One run per case.** §14.6 used the same budget. The per-case ZIX differences here are
  mostly smaller than the ~1.0 unit-length measurement error of §14.2 and should not be read
  individually; the aggregates and the fidelity counts are what carry.
* **The baseline samples, the loop does not.** `main` set no `temperature`, so the baseline
  runs at the server default while the loop's pass 1 is at 0.0. This is faithful to `main`
  and it means the baseline's numbers carry sampling variance the loop's do not.
* **LLM judges have length bias**, and the loop's outputs are consistently the longer ones.
  That is a reason to weigh the judges' *concrete, quotable* findings (a dropped
  Geschäftsnummer, a missing name) over their verdict counts — and the fidelity metrics in
  §15.3, which are measured rather than judged, point the same way.
* **The corpus over-represents CHUNKED** (9 long documents to 7 short, §12 expects the
  reverse in production). On the seven WHOLE cases the two systems are much closer: same
  band outcome (5 `easy`, 2 `ok`), 4 facts lost each. **Most of the redesign's measured
  value is on long documents.**

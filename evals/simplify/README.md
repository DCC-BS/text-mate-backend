# Simplify eval corpus

Corpus for the simplify eval harness (`src/text_mate_tools/run_simplify_eval.py`,
`src/text_mate_tools/simplify_eval/`). Methodology: [`docs/simplify_redesign.md` §6](../../docs/simplify_redesign.md).

## What is here

16 cases: **12 real published Basel-Stadt Grosser-Rat documents**, 3 adapted from the
advisor corpus, 1 synthetic. Every case declares which it is in a `provenance` field, so
nobody has to guess whether a number is evidence.

| provenance | count | what it means |
|---|---|---|
| `real` | 12 | verbatim text of a published document, `source_url` given. **Evidence.** |
| `adapted` | 3 | real Behörden register, reused from `evals/advisor/cases/`, not a published document |
| `synthetic` | 1 | written for the harness. Illustrates that the code path runs; proves nothing about Behörden prose |

`SimplifyEvalCase.provenance` defaults to `synthetic` on purpose: a case that forgets to
declare itself must understate its authority, never overstate it.

### The real documents

Twelve Ratschläge, Anzüge, Schriftliche Anfragen, Volksinitiativen and Berichte from
[grosserrat.bs.ch](https://grosserrat.bs.ch), converted from PDF with the project's own
docling service and flattened to the blank-line-separated plain text the editor sends
(`editor.getText()`). Each case's `source_url` links the original PDF.

**All twelve score `hard`** — ZIX −3.30 to −5.70, CEFR C1/C2. This is the corpus's whole
point: the seed corpus was easy enough that a single rewrite pass reached target on every
case, so no configuration could be told apart from any other. Ten of the twelve sit more
than 3.2 ZIX below the target floor, further than one rewrite pass was observed to travel.

A thirteenth document (`000000412714`, Bericht der Finanzkommission zur Jahresrechnung
2025) was converted but **deliberately excluded**: at 168,000 characters it is well past
the editor's own 100,000-character input limit, so it is not a document the pipeline can
ever be handed.

## ⚠️ Still outstanding

- **Case count.** 16 of the 20–30 the spec asks for.
- **Band coverage is one-sided.** 13 `hard`, 2 `ok`, 1 `easy` — and every `hard` case is a
  real document while the easy end is adapted or synthetic. The corpus can now show that a
  simplifier fails to reach target; it is thin on showing that a simplifier leaves an
  already-easy text alone. Real Basel-Stadt texts that are *already* B1 (bs.ch service
  pages, Einfache-Sprache material) would close this.
- **Mode balance is inverted versus production.** 12 CHUNKED to 4 WHOLE, because
  parliamentary documents are long. §12 expects WHOLE for the large majority of real
  requests, so aggregate numbers should be read per mode, never pooled.
- ~~Every must-keep fact is auto-extracted and unreviewed.~~ **Done:** all 16 cases carry
  `must_keep_facts_reviewed: true`, seven of them corrected in the process
  (see `docs/simplify_redesign.md` §6). The paragraph further down that still describes the
  facts as candidates is about how to add a *new* case.

Nothing here was scraped: the 14 PDFs were supplied directly, downloaded once to a scratch
directory, and are not committed — only the extracted text lives in git.

## Case schema

One JSON object per file in `cases/`, validated by
`text_mate_tools.simplify_eval.models.SimplifyEvalCase`. By convention the filename stem
equals the `id`.

| Field | Type | Required | Meaning |
|---|---|---|---|
| `id` | string | yes | Unique case identifier |
| `source_text` | string | yes | The verbatim source, paragraphs separated by blank lines (`\n\n`) — the form the client sends |
| `language` | string | no (`"de"`) | ISO 639-1 code of the text |
| `source_score` | number \| null | no (`null`) | Readability score of the source when authored (ZIX for German) |
| `source_band` | `"easy"` \| `"ok"` \| `"hard"` \| null | no (`null`) | Band of `source_score` |
| `notes` | string | no (`""`) | What the case is probing |
| `provenance` | `"real"` \| `"adapted"` \| `"synthetic"` | no (`"synthetic"`) | Where the text came from |
| `source_url` | string | required when `provenance` is `"real"` | URL of the published document |
| `source_document` | string | no (`""`) | Title or filename of the source |
| `must_keep_facts` | string[] | no (`[]`) | Verbatim substrings of `source_text` that must survive simplification |
| `must_keep_facts_reviewed` | boolean | no (`false`) | Whether a **human** has checked those facts |

Notes on the fields that are easy to get wrong:

- **`source_score` / `source_band` are optional and are *not* ground truth.** Unlike the
  advisor corpus there is nothing to hand-label: the analyzer is itself the scorer (§6).
  They are a recorded observation, useful for spotting drift when the analyzer changes. A
  case with both `null` is valid and gets scored at runtime — never block on collecting
  scores. When both are given for a German case they must agree: `easy` ⇔ ZIX ≥ 0, `ok` ⇔
  −2 ≤ ZIX < 0, `hard` ⇔ ZIX < −2 (§2.1, §1.1).
- **`must_keep_facts` are candidates, not ground truth, until reviewed.** Every fact in
  this corpus was extracted programmatically — dates, deadlines, CHF amounts,
  Geschäftsnummern, percentages, named bodies — and **none has been reviewed by a human**.
  A regex can tell that `15. Dezember 2026` is a date; it cannot tell whether losing it
  changes what the document means. Treat fidelity numbers over unreviewed facts as
  indicative. Reviewing a case means reading its facts, deleting the incidental ones,
  adding what the extractor missed, and setting `must_keep_facts_reviewed: true`.
- Facts must be exact substrings of `source_text`; the validator rejects anything else,
  because a fact absent from the source could never be found in the output either.
  Comparison at measurement time is normalized (`simplify_eval/normalize.py`), so
  `dreissig Tagen` → `30 Tagen` is not reported as a loss.
- **Mode is derived, not declared.** A case runs CHUNKED iff `len(source_text) > 8000`
  (`--threshold` overrides, §9).

Example (trimmed):

```json
{
  "id": "bs-gr-anzug-feuerwerks-littering",
  "source_text": "An den Grossen Rat\n\nBVD/P265065\n\nBasel, 1. Juli 2026\n\n…",
  "language": "de",
  "source_score": -3.3,
  "source_band": "hard",
  "notes": "Anzug Michael Graber und Konsorten betreffend «Feuerwerks-Littering». …",
  "provenance": "real",
  "source_url": "https://grosserrat.bs.ch/dokumente/100412/000000412940.pdf",
  "source_document": "Anzug Michael Graber und Konsorten betreffend «Feuerwerks-Littering»",
  "must_keep_facts": ["22. April 2026", "30. Juni 2026", "Bau- und Verkehrsdepartement"],
  "must_keep_facts_reviewed": false
}
```

## Adding a case

1. Get a **real, public** Basel-Stadt text. For a PDF, convert it with the project's
   docling service rather than a new PDF library — `DocumentConversionService` is the same
   wrapper `POST /convert/doc` uses. Flatten the result to plain text with blocks joined by
   blank lines; the eval must measure the shape the pipeline actually receives.
2. Strip conversion wreckage: dotted-leader tables of contents, bare page numbers, blocks
   with no letters in them. Keep real headings — the pipeline has to cope with them.
3. Write `cases/<id>.json` with at least `id` and `source_text`, and set `provenance` and
   `source_url` honestly.
4. List facts that must survive in `must_keep_facts`, copied character-for-character out of
   `source_text`. Set `must_keep_facts_reviewed: true` only if a human read them.
5. Optionally record `source_score` / `source_band`. For German:

   ```bash
   uv run python -c "import json,sys; from text_mate_backend.readability import get_analyzer; \
   a=get_analyzer('de'); t=json.load(open(sys.argv[1]))['source_text']; s=a.score(t); \
   print(round(s,3), a.band(s), a.cefr(s))" evals/simplify/cases/<id>.json
   ```

   The analyzer is a local CPU model — no LLM and no network needed.
6. Validate. This checks schema, must-keep facts, score/band agreement and `real`-without-
   `source_url`, then prints what the corpus spans and where it falls short:

   ```bash
   uv run python -m text_mate_tools.run_simplify_eval --simplifier none
   ```

7. Get source-side numbers without an LLM:

   ```bash
   uv run python -m text_mate_tools.run_simplify_eval --simplifier passthrough
   ```

Run everything from the repository root so `evals/` resolves.

## Language coverage

The corpus is **German**. The harness is language-parameterised, but only German is
measured against real data; `en` / `fr` / `it` correctness rests on the readability unit
tests ported from blokkli (§4.2), not on anything measured here. The report prints this
caveat in its header. Do not read a German number as a claim about the other three.

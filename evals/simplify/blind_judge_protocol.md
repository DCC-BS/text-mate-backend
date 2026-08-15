# Blind A/B judge protocol

The instructions handed to each LLM judge in the taste comparison. Companion to
`src/text_mate_tools/simplify_eval/build_blind_pairs.py`, which produces the tree they
read. ZIX says whether a text got easier; this says whether it is a text a Basel-Stadt
department could actually send out — a different question, and one no formula answers.

## What the judge is given

A directory per case, holding `original.txt`, `A.txt` and `B.txt`. **A and B are two
different systems' rewrites of `original.txt`, and which system is A is drawn afresh for
every case.** Nothing in the tree identifies either system, and the key lives outside it.

Judges are told the assignment is per-case precisely so they cannot carry a guess from one
case to the next: a judge who decides "A is the careful one" on case 1 and applies it to
the other 15 has produced one datapoint, not sixteen.

## The instructions (verbatim)

> You are judging two German rewrites of a Basel-Stadt administration document, in the
> context of the cantonal administration of Basel-Stadt (Grosser Rat documents, Merkblätter,
> official letters). The goal of both rewrites is **Einfache Sprache, level B1–A2**, with
> all information preserved.
>
> For each case directory you will find `original.txt`, `A.txt` and `B.txt`. **Which system
> produced A and which produced B is randomised separately for every case** — you cannot
> infer it, and a preference for a letter carried across cases is a bias, not a finding.
> You are not told what either system is, and you should not speculate.
>
> For documents over ~8000 characters, read the first ~6000 characters of each side plus
> the corresponding part of the original; say so in your notes rather than pretending to
> have read the whole thing.
>
> Judge from your role's priorities (below). For each case, output one line:
>
>     <case_id> | A | B | tie — <one sentence, naming the concrete thing that decided it>
>
> (Pick exactly one of A / B / tie.) A tie is a real verdict: use it when the difference
> would not change whether you'd sign the text off. Then give:
>
> 1. **Tally** — A wins, B wins, ties.
> 2. **Systematic differences** — what one side does that the other consistently does not.
>    Quote German fragments; a claim without a quote is an impression.
> 3. **Worst three failures you saw, on either side**, with the quote and why it matters
>    for a Basel-Stadt reader.
> 4. **Would you sign either off as-is?** Separately for A-side and B-side texts, in one
>    sentence each.

## The four roles

Deliberately not four flavours of "which is better written". Each role has an interest
that can *conflict* with the others — the accessibility specialist wants sentences the
jurist thinks are legally lossy — so agreement between them is informative and
disagreement localises the trade-off rather than averaging it away.

| Role | Priority | The failure it is there to catch |
|---|---|---|
| **Verwaltungsjurist:in** (legal officer, Basel-Stadt) | Legal fidelity: deadlines, amounts, Geschäftsnummern, conditions, who owes whom what | A simplification that changed the legal meaning, dropped a qualifier, or turned "kann" into "muss" |
| **Fachperson Einfache Sprache** (accessibility specialist) | The B1–A2 rule set as actually taught: sentence length, one idea per sentence, no nominalisation, explained jargon | A text that scores well but still reads as Behördendeutsch with shorter sentences |
| **Kommunikationsverantwortliche:r Staatskanzlei** | Register and house style: correct Sie-form, Swiss orthography, «» quotes, CHF/date/time conventions, a tone the canton can publish | Something formally correct that embarrasses the canton, or breaks house style |
| **Betroffene:r Bürger:in** (reader with limited German, no administrative background) | Can I tell what this means for me, what I must do, and by when? | A text that is grammatically simple but leaves the reader unsure what to do |

## Reading the result

Four judges × 16 cases is 64 verdicts, and they are **not** independent measurements of one
quantity: the roles disagree by construction. Report per-role tallies, never a pooled
score. A 3-1 split across roles is the interesting result, not noise to be averaged out.

Judges are LLMs reading German administrative prose, and are subject to the usual
LLM-judge failure modes — length bias, preference for the more fluent surface. Their
verdicts are qualitative evidence to be read alongside the ZIX numbers, not a measurement
that overrides them.

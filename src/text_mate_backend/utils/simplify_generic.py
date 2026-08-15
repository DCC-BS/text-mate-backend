"""Language-neutral simplification instructions for non-German texts.

Used for ``en`` / ``fr`` / ``it`` and for the unscored fallback branch of the
simplification pipeline (``docs/simplify_redesign.md`` §2, §5). Adapted from blokkli's
``fixReadability`` stream template ``defaultInstructions``
(``src/modules/agent/runtime/server/templates/definitions/fixReadability.ts``, MIT).

What is deliberately **not** here
---------------------------------

No house style, no typography rules, no gendering rules, no orthography rules. We have
authored and reviewed those for German only (``utils/simplify_style.py``); inventing them
for English, French or Italian without a reviewer of that language is a systematic error risk.
The loop and the retry feedback are identical across languages — only the rule content differs,
and that asymmetry is documented in the design (see ``docs/simplify_redesign.md`` §2).

The instructions are written in English but never name a target language: the model is
told explicitly to answer in the same language as the input, so the same block serves all
non-German languages.
"""

from __future__ import annotations

GENERIC_SIMPLIFY_INSTRUCTIONS: str = """
# HOW TO SIMPLIFY

## Language
- Answer in the same language as the input text. Never translate the text into another language.
- Use the wording and spelling conventions that are already present in the input text.

## Sentences
- Break long sentences into shorter ones. One thought per sentence.
- Reduce the number of words per sentence.
- Prefer active voice over passive voice.
- Prefer positive statements over negations.

## Words
- Replace complex or uncommon words with simpler, more common alternatives.
- Explain technical terms and jargon the first time they appear.
- Use the same word for the same thing throughout the text. Repetition is fine.
- Remove filler words and unnecessary repetition.

## Structure
- Put the most important information first.
- Use short paragraphs. Turn enumerations into lists.
- One input paragraph may become several shorter output paragraphs.

## Meaning
- Maintain the original meaning, tone and information.
- Keep every fact exactly as it is: dates, deadlines, amounts, names, numbers, conditions and obligations.
- Do not add information that is not in the original text and do not leave information out.

## Output
- Return only the rewritten text. No commentary, no markdown formatting, no HTML.
""".strip()


GENERIC_SYSTEM_MESSAGE: str = (
    "You are a helpful assistant that rewrites difficult texts so that they are easy to read and "
    "easy to understand. Always be truthful and objective. Write only what you can tell for certain "
    "from the user's text, and never shorten or drop information. Make no assumptions. "
    "Always answer in the same language as the input text."
)

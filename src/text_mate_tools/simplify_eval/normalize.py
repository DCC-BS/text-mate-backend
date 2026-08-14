"""Normalization for the must-keep-facts measurement (docs/simplify_redesign.md §6).

The harness checks that hand-listed facts — dates, deadlines, amounts, names — survive
simplification. A naive substring test reports **phantom losses**, because a good
simplification legitimately reformats exactly the things we are checking:

===============================  ===============================  ==================
Source                           Simplified                       Same fact?
===============================  ===============================  ==================
``innert dreissig Tagen``        ``innert 30 Tagen``              yes — Bundeskanzlei
                                                                  rules *require*
                                                                  digits for
                                                                  quantities
``40.50 Franken``                ``Fr. 40.50``                    yes
``30. Juni 2025``                ``30.06.2025``                   yes
``1'000 Franken``                ``CHF 1000``                     yes
===============================  ===============================  ==================

Every row above was reported as a lost fact by the exact-substring check, and chasing
those phantoms is what triggered the review that removed the runtime fidelity gate. So
both sides are normalized to a canonical form before comparing.

This is a **measurement**, never a gate: nothing in the request path imports this module.
It is tuned to under-report losses rather than over-report them — a missed real loss costs
one line of a report that a human reads, whereas a phantom loss costs an investigation.

Known limits, deliberately not fixed: compound number words (``einundzwanzig``) are not
expanded, the bare articles ``ein``/``eine``/``einen`` are left alone (turning them into
``1`` would mangle ordinary prose), and only German number words are covered — the corpus
is German (§6).
"""

from __future__ import annotations

import re
from typing import Final

#: German number words the corpus actually uses, plus the obvious neighbours. Swiss
#: spelling (``dreissig``) and German spelling (``dreißig``) both map to the digit; the
#: text is lowercased and ``ß``-folded before lookup, so only one form is needed here.
NUMBER_WORDS: Final[dict[str, str]] = {
    "null": "0",
    "eins": "1",
    "zwei": "2",
    "drei": "3",
    "vier": "4",
    "fuenf": "5",
    "sechs": "6",
    "sieben": "7",
    "acht": "8",
    "neun": "9",
    "zehn": "10",
    "elf": "11",
    "zwoelf": "12",
    "dreizehn": "13",
    "vierzehn": "14",
    "fuenfzehn": "15",
    "sechzehn": "16",
    "siebzehn": "17",
    "achtzehn": "18",
    "neunzehn": "19",
    "zwanzig": "20",
    "dreissig": "30",
    "vierzig": "40",
    "fuenfzig": "50",
    "sechzig": "60",
    "siebzig": "70",
    "achtzig": "80",
    "neunzig": "90",
    "hundert": "100",
    "tausend": "1000",
}

#: German month names -> month number, for date canonicalization.
MONTHS: Final[dict[str, int]] = {
    "januar": 1,
    "februar": 2,
    "maerz": 3,
    "april": 4,
    "mai": 5,
    "juni": 6,
    "juli": 7,
    "august": 8,
    "september": 9,
    "oktober": 10,
    "november": 11,
    "dezember": 12,
}

#: Every way the corpus writes Swiss francs. All collapse to ``chf``.
CURRENCY_WORDS: Final[tuple[str, ...]] = ("franken", "chf", "fr.", "fr", "sfr.", "sfr")

_AMOUNT = r"\d+(?:[.,'’\s]\d+)*"

_CURRENCY_ALTERNATION = "|".join(re.escape(word) for word in CURRENCY_WORDS)
_CURRENCY_BEFORE = re.compile(rf"(?<!\w)(?:{_CURRENCY_ALTERNATION})\s*({_AMOUNT})(?!\w)")
_CURRENCY_AFTER = re.compile(rf"(?<!\w)({_AMOUNT})\s*(?:{_CURRENCY_ALTERNATION})(?!\w)")

_DATE_WITH_MONTH_NAME = re.compile(
    rf"(?<!\d)(\d{{1,2}})\.\s*({'|'.join(MONTHS)})\.?(?:\s+(\d{{2,4}}))?(?!\w)",
)
_DATE_NUMERIC = re.compile(r"(?<!\d)(\d{1,2})\.\s*(\d{1,2})\.\s*(\d{2,4})(?!\d)")

_NUMBER_WORD = re.compile(rf"(?<!\w)({'|'.join(NUMBER_WORDS)})(?!\w)")

_THOUSANDS = re.compile(r"(?<=\d)[\s'’](?=\d{3}(?!\d))")
_DECIMAL_COMMA = re.compile(r"(?<=\d),(?=\d)")
_NOISE = re.compile(r"[^\w.]+")
_SPACES = re.compile(r"\s+")


def _fold(text: str) -> str:
    """Lowercase and fold German-specific characters, so one table covers both spellings.

    >>> _fold("Dreißig Franken über zwölf Jahre")
    'dreissig franken ueber zwoelf jahre'
    """
    folded = text.lower().replace("ß", "ss")
    for umlaut, replacement in (("ä", "ae"), ("ö", "oe"), ("ü", "ue")):
        folded = folded.replace(umlaut, replacement)
    return folded


def _canonical_amount(raw: str) -> str:
    """``"1'000.50"`` and ``"1 000,50"`` both become ``"1000.50"``.

    >>> _canonical_amount("1'000,50"), _canonical_amount("40.50")
    ('1000.50', '40.50')
    """
    amount = _THOUSANDS.sub("", raw.strip())
    amount = _DECIMAL_COMMA.sub(".", amount)
    return _SPACES.sub("", amount)


def _canonical_date(day: str, month: int, year: str | None) -> str:
    """``d.m.yyyy`` with no leading zeros; a two-digit year is expanded to 20xx.

    >>> _canonical_date("30", 6, "2025"), _canonical_date("01", 6, None)
    ('30.6.2025', '1.6.')
    """
    parts = f"{int(day)}.{month}."
    if year is None:
        return parts
    numeric_year = int(year)
    if numeric_year < 100:
        numeric_year += 2000
    return f"{parts}{numeric_year}"


def normalize_for_fact_match(text: str) -> str:
    """Canonicalize ``text`` so equivalent renderings of a fact compare equal.

    >>> normalize_for_fact_match("innert dreissig Tagen")
    'innert 30 tagen'
    >>> normalize_for_fact_match("40.50 Franken") == normalize_for_fact_match("Fr. 40.50")
    True
    >>> normalize_for_fact_match("30. Juni 2025") == normalize_for_fact_match("30.06.2025")
    True
    >>> normalize_for_fact_match("1'000 Franken") == normalize_for_fact_match("CHF 1000")
    True
    >>> normalize_for_fact_match("Die Frist beträgt  sechzig Tage!")
    'die frist betraegt 60 tage'
    """
    folded = _fold(text)

    # Dates first: they own the "12.3.2025" shape, which the amount rules would
    # otherwise chew into a decimal.
    folded = _DATE_WITH_MONTH_NAME.sub(
        lambda m: _canonical_date(m.group(1), MONTHS[m.group(2)], m.group(3)),
        folded,
    )
    folded = _DATE_NUMERIC.sub(lambda m: _canonical_date(m.group(1), int(m.group(2)), m.group(3)), folded)

    # Currency next, so "Fr. 40.50" and "40.50 Franken" become one token order.
    folded = _CURRENCY_BEFORE.sub(lambda m: f"chf {_canonical_amount(m.group(1))}", folded)
    folded = _CURRENCY_AFTER.sub(lambda m: f"chf {_canonical_amount(m.group(1))}", folded)

    folded = _NUMBER_WORD.sub(lambda m: NUMBER_WORDS[m.group(1)], folded)
    folded = _THOUSANDS.sub("", folded)
    folded = _DECIMAL_COMMA.sub(".", folded)

    # Drop remaining punctuation but keep '.', which carries decimals and dates.
    folded = _NOISE.sub(" ", folded)
    folded = _SPACES.sub(" ", folded).strip()
    # A trailing sentence dot is punctuation, not a decimal point.
    return folded.rstrip(".")


def fact_survives(fact: str, text: str) -> bool:
    """Whether ``fact`` is present in ``text``, ignoring legitimate reformatting.

    >>> fact_survives("dreissig Tagen", "Sie haben innert 30 Tagen Zeit.")
    True
    >>> fact_survives("40.50 Franken", "Die Gebuehr betraegt Fr. 40.50.")
    True
    >>> fact_survives("30. Juni 2025", "Bis 30.06.2025 einreichen.")
    True
    >>> fact_survives("250 Franken", "Es kostet nichts.")
    False
    """
    normalized_fact = normalize_for_fact_match(fact)
    if not normalized_fact:
        return True
    return normalized_fact in normalize_for_fact_match(text)


def missing_facts(facts: list[str], text: str) -> list[str]:
    """The facts of ``facts`` that ``text`` does not contain, in their original wording.

    >>> missing_facts(["dreissig Tagen", "250 Franken"], "Innert 30 Tagen, kostenlos.")
    ['250 Franken']
    """
    return [fact for fact in facts if not fact_survives(fact, text)]

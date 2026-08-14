"""Unit tests for the simplification prompt blocks and the reconciled German rules.

Covers Phase 3 of ``docs/simplify_redesign.md``:

* T3.1 — the reconciled ``RULES_ES`` no longer contradicts Basel-Stadt / Bundeskanzlei,
  and ``PlainLanguageAgent``'s imports still work.
* T3.2 — ``SIMPLIFY_STYLE_DE`` carries the rules of all three sources, deduplicated.
* T3.3 — the generic prompt is language-neutral and carries no authored style rules.
* T3.4 — the composable prompt renderers and their assembly.

No LLM, no I/O: everything here is pure string construction.
"""

from text_mate_backend.utils.easy_language import (
    CLAUDE_TEMPLATE_ES,
    REWRITE_COMPLETE,
    RULES_ES,
    SYSTEM_MESSAGE_ES,
)
from text_mate_backend.utils.simplify_generic import GENERIC_SIMPLIFY_INSTRUCTIONS, GENERIC_SYSTEM_MESSAGE
from text_mate_backend.utils.simplify_prompt import (
    MAX_EXAMPLE_CHARS,
    MAX_ORIGINAL_CHARS,
    NeighbourContext,
    ParagraphIssue,
    PassingExample,
    PreviousAttempt,
    ScoreReference,
    build_rewrite_prompt,
    build_system_message,
    escalation_instructions,
    is_german,
    render_issue_list,
    render_neighbour_context,
    render_passing_examples,
    render_retry_block,
    render_score_reference_block,
    select_rules,
)
from text_mate_backend.utils.simplify_style import SIMPLIFY_STYLE_DE


class TestPlainLanguageAgentContract:
    """The live quick action must keep working (spec: do not break the feature)."""

    def test_imports_are_non_empty_strings(self) -> None:
        for constant in (CLAUDE_TEMPLATE_ES, REWRITE_COMPLETE, RULES_ES, SYSTEM_MESSAGE_ES):
            assert isinstance(constant, str)
            assert constant.strip()

    def test_template_still_formats_with_the_same_placeholders(self) -> None:
        prompt = CLAUDE_TEMPLATE_ES.format(prompt="Ein Text.", completeness=REWRITE_COMPLETE, rules=RULES_ES)
        assert "Ein Text." in prompt
        assert RULES_ES in prompt


class TestReconciledRulesEs:
    """T3.1 — every clause the audit deleted is gone; the BS/BK form replaced it."""

    def test_null_rappen_uses_gedankenstrich(self) -> None:
        # bundeskanzlei: "Franken und Rappen mit Punkt, fehlende Rappen mit Gedankenstrich"
        assert "Fr. 20.–" in RULES_ES
        assert "Anstatt des Null-Rappen-Strichs" not in RULES_ES
        # "CHF" was the reverted mandate (audit §3b); it must not appear at all, so this
        # cannot be a stray leftover of the old "CHF 20.00" counter-example either.
        assert "CHF" not in RULES_ES
        assert "EUR 14,90" not in RULES_ES

    def test_units_use_digits_and_abbreviations(self) -> None:
        # Percent signs get no space; units of measure get a space; common units may be
        # abbreviated, all others spelled out (audit §5 checklist item 1, row 16).
        assert "«30%»" in RULES_ES
        assert "«30 %»" not in RULES_ES
        assert "«30 Prozent» statt «30 %»" not in RULES_ES
        assert "«2 Meter» statt «2 m»" not in RULES_ES
        assert "«200 Kilometer pro Stunde» statt «200 km/h»" not in RULES_ES
        assert "«5 t»" in RULES_ES and "«10 m»" in RULES_ES and "«2 Tonnen»" in RULES_ES

    def test_full_hours_have_no_minutes(self) -> None:
        # bundeskanzlei: "Volle Stunden ohne Minutenangabe"
        assert "14 Uhr (NICHT 14.00 Uhr)" in RULES_ES
        assert "Ergänze immer .00 bei vollen Stunden" not in RULES_ES
        assert "14.00 Uhr (NICHT 14 Uhr)" not in RULES_ES

    def test_gendering_bans_forbidden_forms(self) -> None:
        # bundeskanzlei: "Verbotene Genderschreibweisen"; house style section 2
        for forbidden in ("Bürger*innen", "Bürger:innen", "BürgerInnen", "Bürger(innen)", "Bürger/-innen"):
            assert forbidden in RULES_ES
        assert "sprachliche Gleichbehandlung von Mann und Frau" not in RULES_ES

    def test_currency_uses_fr_before_exact_amounts_and_franken_in_running_text(self) -> None:
        # Reviewer sign-off (audit §5 checklist item 5, reversing §3b): actual Basel-Stadt
        # practice, matching the Bundeskanzlei's own examples (BK 10, BK 11: "Fr. 327.65",
        # "Fr. 20.–"), is «Fr.» before an exact figure and «Franken» spelled out in running
        # prose. The CHF mandate is gone, and so is the clause that forbade «Fr.».
        for rules in (RULES_ES, SIMPLIFY_STYLE_DE):
            assert "als Währungseinheit «Fr.»" in rules
            assert "Die Abkürzung «Fr.» verwendest du NIE" not in rules
            assert "als Währungseinheit immer «CHF»" not in rules
            assert "CHF" not in rules
            assert "Fr. 327.65" in rules

    def test_currency_rule_has_a_worked_before_after_example(self) -> None:
        for rules in (RULES_ES, SIMPLIFY_STYLE_DE):
            assert "aus «40.50 Franken» wird «Fr. 40.50»" in rules
            assert "NICHT 40.50 Franken" in rules

    def test_stumme_e_rule_is_deleted(self) -> None:
        # Audit §5 checklist item 3: row 17 (stummes "e" am Wortende) was a Zurich
        # idiosyncrasy with no BS/BK backing, named and dropped on human review; row 12
        # (Substantivierungen vermeiden) stays.
        for rules in (RULES_ES, SIMPLIFY_STYLE_DE):
            assert "stumme" not in rules
            assert "des Fahrzeugs" not in rules
            assert "des Fahrzeuges" not in rules
        assert "Vermeide Substantivierungen" in RULES_ES

    def test_kept_strengths_survive(self) -> None:
        for kept in (
            "höchstens 12 Wörtern",
            "einen Gedanken pro Satz",
            "aktive Sprache anstelle von Passiv",
            "positiv und bejahend",
            "häufig gebräuchliche Wörter",
            "Benenne Gleiches immer gleich",
            "Erkläre Fachbegriffe",
            "Vermeide Substantivierungen",
            "Motorfahrzeug-Ausweispflicht",
        ):
            assert kept in RULES_ES

    def test_swiss_orthography(self) -> None:
        assert "ß" not in RULES_ES
        assert "ß" not in SYSTEM_MESSAGE_ES
        assert "«" in RULES_ES and "»" in RULES_ES


class TestSimplifyStyleDe:
    """T3.2 — composed from all three sources, deduplicated, Swiss orthography."""

    def test_house_style_rules_present(self) -> None:
        for rule in ("«Sie»", "Paarformen", "Gendersternchen", "«ss»", "Anglizismen"):
            assert rule in SIMPLIFY_STYLE_DE

    def test_merkblatt_rules_present(self) -> None:
        for rule in ("Floskeln", "Amtsdeutsch", "Schachtelsätze", "Gedanken pro Satz", "auf Augenhöhe"):
            assert rule in SIMPLIFY_STYLE_DE

    def test_surviving_rules_es_rules_present(self) -> None:
        for rule in ("höchstens 12 Wörtern", "Benenne Gleiches immer gleich", "Fr. 20.–", "«30%»"):
            assert rule in SIMPLIFY_STYLE_DE

    def test_deduplicated(self) -> None:
        # These appear in two or three sources and must appear exactly once here.
        assert SIMPLIFY_STYLE_DE.count("Gedanken pro Satz") == 1
        assert SIMPLIFY_STYLE_DE.count("höchstens 12 Wörtern") == 1
        assert SIMPLIFY_STYLE_DE.count("Benenne Gleiches immer gleich") == 1

    def test_agrees_with_the_reconciled_rules(self) -> None:
        # The only Eszett allowed is the one inside the rule that forbids it.
        assert SIMPLIFY_STYLE_DE.count("ß") == 1
        assert "immer «ss», nie «ß»" in SIMPLIFY_STYLE_DE
        # "Fr. 20.00" and "14.00 Uhr" may appear only as counter-examples; CHF is gone.
        assert "Fr. 20.– (NICHT Fr. 20.00, NICHT Fr. 20,–)" in SIMPLIFY_STYLE_DE
        assert "CHF" not in SIMPLIFY_STYLE_DE
        assert "14 Uhr (NICHT 14.00 Uhr)" in SIMPLIFY_STYLE_DE
        assert SIMPLIFY_STYLE_DE.count("14.00 Uhr") == 1


class TestGenericInstructions:
    """T3.3 — language-neutral, and free of unreviewed style rules."""

    def test_answers_in_the_same_language(self) -> None:
        assert "same language as the input" in GENERIC_SIMPLIFY_INSTRUCTIONS
        assert "same language as the input" in GENERIC_SYSTEM_MESSAGE

    def test_carries_the_blokkli_core_moves(self) -> None:
        for move in (
            "Break long sentences",
            "Replace complex or uncommon words",
            "Reduce the number of words per sentence",
            "Maintain the original meaning",
        ):
            assert move in GENERIC_SIMPLIFY_INSTRUCTIONS

    def test_has_no_house_style_typography_or_gendering_rules(self) -> None:
        for forbidden in ("Basel", "Guillemets", "«", "Paarform", "CHF", "Bundeskanzlei", "gender"):
            assert forbidden not in GENERIC_SIMPLIFY_INSTRUCTIONS


class TestLanguageSelection:
    def test_is_german(self) -> None:
        assert is_german("de") and is_german("DE") and is_german("de-CH")
        assert not is_german("en") and not is_german("fr") and not is_german("it")
        assert not is_german(None) and not is_german("")

    def test_select_rules(self) -> None:
        assert select_rules("de") is SIMPLIFY_STYLE_DE
        for other in ("en", "fr", "it", None):
            assert select_rules(other) is GENERIC_SIMPLIFY_INSTRUCTIONS

    def test_system_message(self) -> None:
        assert build_system_message("de") is SYSTEM_MESSAGE_ES
        assert build_system_message("fr") is GENERIC_SYSTEM_MESSAGE


class TestScoreReferenceBlock:
    def test_empty_without_data(self) -> None:
        assert render_score_reference_block(None, "de") == ""

    def test_renders_score_band_cefr_and_table(self) -> None:
        block = render_score_reference_block(
            ScoreReference(
                label="ZIX",
                score=-3.84,
                band="hard",
                cefr="C1",
                scale="-10 bis 10",
                target="Sprachniveau A2 oder B1 (ZIX 0 oder höher)",
                reference_table="A1 ab 4.0, A2 ab 2.0, B1 ab 0.",
            ),
            "de",
        )
        assert block.startswith("<bewertung>") and block.endswith("</bewertung>")
        assert "ZIX, -10 bis 10" in block
        assert "C1 (ZIX -3.8, hard)" in block
        assert "Sprachniveau A2 oder B1" in block
        assert "A1 ab 4.0" in block

    def test_generic_language_uses_english_headings(self) -> None:
        block = render_score_reference_block(ScoreReference(label="LIX", score=52.0), "fr")
        assert block.startswith("<scoring>")
        assert "Current: LIX 52.0." in block


class TestIssueList:
    def test_empty_without_issues(self) -> None:
        assert render_issue_list([], "ZIX", "de") == ""

    def test_quotes_paragraph_with_index_score_band_and_impact(self) -> None:
        block = render_issue_list(
            [
                ParagraphIssue(index=2, text="Erster Absatz.", score=-4.1, band="hard", impact="hoch"),
                ParagraphIssue(index=5, text="Zweiter Absatz."),
            ],
            "ZIX",
            "de",
        )
        assert "- Absatz 2: «Erster Absatz.» [ZIX -4.1, hard, Auswirkung: hoch]" in block
        assert "- Absatz 5: «Zweiter Absatz.»" in block
        assert "[]" not in block

    def test_truncates_long_paragraphs(self) -> None:
        block = render_issue_list([ParagraphIssue(index=1, text="x" * 900)], "ZIX", "de")
        assert "x" * MAX_ORIGINAL_CHARS + "..." in block
        assert "x" * (MAX_ORIGINAL_CHARS + 1) not in block


class TestRetryBlock:
    def test_empty_on_first_attempt(self) -> None:
        assert render_retry_block(None, "ZIX", "de") == ""

    def test_contains_previous_attempt_score_and_missing_facts(self) -> None:
        block = render_retry_block(
            PreviousAttempt(
                attempt=1,
                text="Meine vorherige Fassung.",
                score=-1.2,
                band="ok",
                missing_facts=["Frist: 30. Juni 2026", "Betrag: CHF 250.–"],
            ),
            "ZIX",
            "de",
        )
        assert "Dein Versuch 1" in block
        assert "ZIX -1.2, ok" in block
        assert "«Meine vorherige Fassung.»" in block
        assert "- Frist: 30. Juni 2026" in block
        assert "- Betrag: CHF 250.–" in block

    def test_no_missing_facts_section_when_fidelity_passed(self) -> None:
        block = render_retry_block(PreviousAttempt(attempt=1, text="Fassung."), "ZIX", "de")
        assert "gefehlt" not in block

    def test_instructions_escalate_between_attempts(self) -> None:
        first = render_retry_block(PreviousAttempt(attempt=1, text="Fassung."), "ZIX", "de")
        second = render_retry_block(PreviousAttempt(attempt=2, text="Fassung."), "ZIX", "de")
        assert "höchstens 12 Wörter pro Satz" in first
        assert "höchstens 10 Wörter pro Satz" in second
        assert first != second

    def test_escalation_is_clamped(self) -> None:
        assert escalation_instructions(0, "de") == escalation_instructions(1, "de")
        assert escalation_instructions(7, "de") == escalation_instructions(2, "de")

    def test_generic_language_escalation(self) -> None:
        block = render_retry_block(PreviousAttempt(attempt=2, text="My version."), "LIX", "en")
        assert block.startswith("<previous-attempt>")
        assert "max 10 words per sentence" in block
        assert "«" not in block

    def test_truncates_previous_attempt(self) -> None:
        block = render_retry_block(PreviousAttempt(attempt=1, text="y" * 900), "ZIX", "de")
        assert "y" * MAX_ORIGINAL_CHARS + "..." in block


class TestPassingExamples:
    def test_empty_without_examples(self) -> None:
        assert render_passing_examples([], "ZIX", "de") == ""

    def test_limited_to_two_by_default(self) -> None:
        block = render_passing_examples(
            [PassingExample(index=i, text=f"Absatz {i}.", score=1.0 + i) for i in range(1, 5)],
            "ZIX",
            "de",
        )
        assert block.count("- Absatz ") == 2
        assert "Absatz 1." in block and "Absatz 2." in block
        assert "Absatz 3." not in block

    def test_truncates_to_the_example_limit(self) -> None:
        block = render_passing_examples([PassingExample(index=1, text="z" * 400)], "ZIX", "de")
        assert "z" * MAX_EXAMPLE_CHARS + "..." in block
        assert "z" * (MAX_EXAMPLE_CHARS + 1) not in block


class TestNeighbourContext:
    def test_empty_without_context(self) -> None:
        assert render_neighbour_context(None, "de") == ""
        assert render_neighbour_context(NeighbourContext(), "de") == ""

    def test_neighbours_are_read_only_and_scope_is_explicit(self) -> None:
        block = render_neighbour_context(
            NeighbourContext(
                previous_text="Der Absatz davor.",
                following_text="Der Absatz danach.",
                document_summary="Merkblatt zur Baubewilligung.",
            ),
            "de",
        )
        assert "Merkblatt zur Baubewilligung." in block
        assert block.count("NICHT umschreiben") == 2
        assert "AUSSCHLIESSLICH" in block

    def test_summary_only(self) -> None:
        block = render_neighbour_context(NeighbourContext(document_summary="Kurzfassung."), "de")
        assert "Kurzfassung." in block
        assert "Vorheriger Absatz" not in block


class TestBuildRewritePrompt:
    def test_single_shot_prompt_has_only_text_and_rules(self) -> None:
        prompt = build_rewrite_prompt("Ein schwer verständlicher Text.", "de")
        assert "<schwer-verständlicher-text>\nEin schwer verständlicher Text.\n</schwer-verständlicher-text>" in prompt
        assert SIMPLIFY_STYLE_DE in prompt
        assert REWRITE_COMPLETE in prompt
        for absent in ("<bewertung>", "<probleme>", "<vorheriger-versuch>", "<gelungene-beispiele>", "<kontext>"):
            assert absent not in prompt

    def test_blocks_appear_in_the_specified_order(self) -> None:
        prompt = build_rewrite_prompt(
            "Text.",
            "de",
            score_reference=ScoreReference(label="ZIX", score=-2.0, band="hard"),
            issues=[ParagraphIssue(index=1, text="Absatz.", score=-4.0)],
            previous_attempt=PreviousAttempt(attempt=1, text="Vorher.", score=-3.0),
            passing_examples=[PassingExample(index=2, text="Gut.", score=1.0)],
            neighbour_context=NeighbourContext(previous_text="Davor."),
        )
        positions = [
            prompt.index("<schwer-verständlicher-text>"),
            prompt.index("<bewertung>"),
            prompt.index("<probleme>"),
            prompt.index("<vorheriger-versuch>"),
            prompt.index("<gelungene-beispiele>"),
            prompt.index("<kontext>"),
            prompt.index(SIMPLIFY_STYLE_DE),
        ]
        assert positions == sorted(positions)
        assert prompt.rstrip().endswith("Gib nur den umgeschriebenen Text aus.")

    def test_score_label_is_shared_by_every_block(self) -> None:
        prompt = build_rewrite_prompt(
            "Text.",
            "de",
            score_reference=ScoreReference(label="ZIX", score=-2.0),
            issues=[ParagraphIssue(index=1, text="Absatz.", score=-4.0)],
            previous_attempt=PreviousAttempt(attempt=1, text="Vorher.", score=-3.0),
            passing_examples=[PassingExample(index=2, text="Gut.", score=1.0)],
        )
        assert prompt.count("ZIX ") >= 4
        assert "score " not in prompt

    def test_non_german_prompt_uses_generic_rules_only(self) -> None:
        prompt = build_rewrite_prompt(
            "Un texte difficile.",
            "fr",
            score_reference=ScoreReference(label="LIX", score=58.0, target="LIX 40 or lower"),
        )
        assert GENERIC_SIMPLIFY_INSTRUCTIONS in prompt
        assert SIMPLIFY_STYLE_DE not in prompt
        assert REWRITE_COMPLETE not in prompt
        assert "<hard-to-read-text>" in prompt
        assert "same language as the input" in prompt

    def test_german_prompt_keeps_swiss_orthography(self) -> None:
        prompt = build_rewrite_prompt(
            "Text.",
            "de",
            score_reference=ScoreReference(label="ZIX", score=0.0),
            previous_attempt=PreviousAttempt(attempt=2, text="Vorher.", missing_facts=["Frist"]),
            neighbour_context=NeighbourContext(following_text="Danach."),
        )
        # Swiss orthography: the only Eszett is the counter-example in the rule banning it.
        assert prompt.count("ß") == 1
        assert "immer «ss», nie «ß»" in prompt
        # French guillemets, never straight quotes.
        assert '"' not in prompt
        assert "«" in prompt and "»" in prompt

    def test_unknown_language_falls_back_to_generic(self) -> None:
        prompt = build_rewrite_prompt("Un texto difícil.", "es")
        assert GENERIC_SIMPLIFY_INSTRUCTIONS in prompt
        assert "<hard-to-read-text>" in prompt

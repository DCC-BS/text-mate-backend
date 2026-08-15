"""Unit tests for the simplify chunker (pure functions, no LLM, no I/O)."""

from text_mate_backend.utils.simplify_chunker import (
    DEFAULT_MIN_UNIT_WORDS,
    DEFAULT_MIN_WORDS,
    TextUnit,
    classify_unit,
    merge_units,
    reassemble,
    reassemble_with_spans,
    rewritable_units,
    split_units,
)

DOCUMENT = """Anmeldung für die Ergänzungsleistungen

Sie müssen sich bis zum 1. Mai 2026 anmelden, wenn Sie Ergänzungsleistungen beziehen möchten.

- Ihren Ausweis
- Den letzten Steuerbescheid

Nach der Anmeldung prüfen wir Ihre Unterlagen und melden uns innerhalb von 30 Tagen bei Ihnen."""


class TestClassifyUnit:
    def test_short_line_without_terminal_punctuation_is_a_heading(self) -> None:
        assert classify_unit("Anmeldung zur Prüfung") == "heading"

    def test_markdown_heading(self) -> None:
        assert classify_unit("## Ihre Unterlagen") == "heading"

    def test_line_ending_in_terminal_punctuation_is_a_paragraph(self) -> None:
        assert classify_unit("Sie müssen sich anmelden.") == "paragraph"
        assert classify_unit("Was Sie mitbringen müssen:") == "paragraph"

    def test_long_single_line_is_a_paragraph_even_without_punctuation(self) -> None:
        long_line = "Diese Zeile ist deutlich zu lang um noch als Überschrift durchzugehen und hat viele Wörter"
        assert classify_unit(long_line) == "paragraph"

    def test_bullet_markers_make_a_list_item(self) -> None:
        for marker in ("-", "*", "•", "–", "+"):
            assert classify_unit(f"{marker} Ihren Ausweis") == "list_item"

    def test_enumeration_markers_make_a_list_item(self) -> None:
        assert classify_unit("1. Ihren Ausweis") == "list_item"
        assert classify_unit("a) Ihren Ausweis") == "list_item"

    def test_multi_line_prose_is_a_paragraph(self) -> None:
        assert classify_unit("Erste Zeile ohne Punkt\nzweite Zeile ohne Punkt") == "paragraph"

    def test_empty_unit_is_a_paragraph(self) -> None:
        assert classify_unit("") == "paragraph"


class TestSplitUnits:
    def test_splits_on_blank_lines_and_indexes_units(self) -> None:
        units = split_units(DOCUMENT)
        assert [unit.index for unit in units] == [0, 1, 2, 3]
        assert [unit.kind for unit in units] == ["heading", "paragraph", "list_item", "paragraph"]

    def test_offsets_point_back_into_the_original_text(self) -> None:
        units = split_units(DOCUMENT)
        for unit in units:
            assert DOCUMENT[unit.start : unit.end] == unit.text

    def test_offsets_survive_extra_blank_lines_and_indentation(self) -> None:
        text = "Erster Absatz mit genügend Wörtern.\n\n\n   Zweiter Absatz mit genügend Wörtern.  "
        units = split_units(text)
        assert len(units) == 2
        for unit in units:
            assert text[unit.start : unit.end] == unit.text
        assert units[1].text.startswith("Zweiter")

    def test_handles_windows_line_endings(self) -> None:
        text = "Erster Absatz mit genügend Wörtern.\r\n\r\nZweiter Absatz mit genügend Wörtern."
        assert len(split_units(text)) == 2

    def test_empty_and_whitespace_only_text_yields_no_units(self) -> None:
        assert split_units("") == []
        assert split_units("\n\n   \n\n") == []

    def test_units_below_min_words_are_unscorable(self) -> None:
        units = split_units("Zu kurz.\n\nDieser Absatz hat genügend Wörter für eine Bewertung.", min_words=5)
        assert units[0].unscorable is True
        assert units[0].rewritable is False
        assert units[1].unscorable is False

    def test_min_words_comes_from_the_analyzer(self) -> None:
        text = "Dieser Absatz hat genau acht Wörter, ungefähr jedenfalls."
        assert split_units(text, min_words=DEFAULT_MIN_WORDS)[0].unscorable is False
        assert split_units(text, min_words=20)[0].unscorable is True

    def test_word_count_is_recorded(self) -> None:
        units = split_units("Ein Satz mit genau sechs Wörtern hier.")
        assert units[0].word_count == 7


class TestRewritableUnits:
    def test_only_scorable_paragraphs_are_rewritable(self) -> None:
        units = split_units(DOCUMENT)
        rewritable = rewritable_units(units)
        assert [unit.index for unit in rewritable] == [1, 3]
        assert all(unit.kind == "paragraph" for unit in rewritable)

    def test_headings_and_lists_pass_through(self) -> None:
        units = split_units(DOCUMENT)
        assert units[0].rewritable is False
        assert units[2].rewritable is False


class TestReassemble:
    def test_without_replacements_the_document_round_trips(self) -> None:
        units = split_units(DOCUMENT)
        assert reassemble(units, {}) == DOCUMENT

    def test_replacements_are_substituted_by_index(self) -> None:
        units = split_units(DOCUMENT)
        result = reassemble(units, {1: "Melden Sie sich bis zum 1. Mai 2026 an."})
        assert "Melden Sie sich bis zum 1. Mai 2026 an." in result
        assert "Anmeldung für die Ergänzungsleistungen" in result
        assert "- Ihren Ausweis" in result

    def test_one_unit_may_become_several_paragraphs(self) -> None:
        units = split_units("Ein sehr langer und verschachtelter Satz mit vielen Nebensätzen darin.")
        assert reassemble(units, {0: "Kurz.\n\nUnd kurz."}) == "Kurz.\n\nUnd kurz."

    def test_units_are_reassembled_in_index_order(self) -> None:
        units = split_units(DOCUMENT)
        shuffled = list(reversed(units))
        assert reassemble(shuffled, {}) == DOCUMENT

    def test_replacement_whitespace_is_normalized(self) -> None:
        units = split_units("Erster Absatz mit genügend Wörtern.\n\nZweiter Absatz mit genügend Wörtern.")
        result = reassemble(units, {0: "  Neuer Text.  \n"})
        assert result == "Neuer Text.\n\nZweiter Absatz mit genügend Wörtern."

    def test_unknown_indexes_in_replacements_are_ignored(self) -> None:
        units = split_units("Ein Absatz mit genügend Wörtern darin.")
        assert reassemble(units, {99: "wird nicht verwendet"}) == "Ein Absatz mit genügend Wörtern darin."


class TestReassembleWithSpans:
    """The text_mate_backend/models/simplify_models.py unconverged_ranges support:

    each unit's span in the *assembled* output, not the source (units that shipped a
    rewrite have a different length than their source; units that passed through
    unchanged do not).
    """

    def test_text_matches_plain_reassemble(self) -> None:
        units = split_units(DOCUMENT)
        text, _ = reassemble_with_spans(units, {})
        assert text == reassemble(units, {})

    def test_unchanged_unit_span_slices_back_to_its_own_text(self) -> None:
        units = split_units(DOCUMENT)
        text, spans = reassemble_with_spans(units, {})
        for unit in units:
            start, end = spans[unit.index]
            assert text[start:end] == unit.text

    def test_rewritten_unit_with_different_length_maps_correctly(self) -> None:
        units = split_units(DOCUMENT)
        replacement = "Melden Sie sich bis zum 1. Mai 2026 an, sonst gibt es kein Geld."
        assert len(replacement) != len(units[1].text)
        text, spans = reassemble_with_spans(units, {1: replacement})
        start, end = spans[1]
        assert text[start:end] == replacement
        # neighbours shift with it but still map correctly
        for unit in units:
            if unit.index == 1:
                continue
            other_start, other_end = spans[unit.index]
            assert text[other_start:other_end] == unit.text

    def test_replacement_that_expands_into_several_paragraphs_maps_the_whole_span(self) -> None:
        units = split_units("Ein sehr langer und verschachtelter Satz mit vielen Nebensätzen darin.")
        text, spans = reassemble_with_spans(units, {0: "Kurz.\n\nUnd kurz."})
        start, end = spans[0]
        assert text[start:end] == "Kurz.\n\nUnd kurz."

    def test_replacement_whitespace_is_normalized_in_the_span_too(self) -> None:
        units = split_units("Erster Absatz mit genügend Wörtern.\n\nZweiter Absatz mit genügend Wörtern.")
        text, spans = reassemble_with_spans(units, {0: "  Neuer Text.  \n"})
        start, end = spans[0]
        assert text[start:end] == "Neuer Text."

    def test_unknown_indexes_in_replacements_are_ignored(self) -> None:
        units = split_units("Ein Absatz mit genügend Wörtern darin.")
        text, spans = reassemble_with_spans(units, {99: "wird nicht verwendet"})
        assert spans.keys() == {0}
        assert text[spans[0][0] : spans[0][1]] == "Ein Absatz mit genügend Wörtern darin."


class TestMergeUnits:
    """docs/simplify_redesign.md section 14.2: merge paragraphs to >= min_unit_words."""

    def test_default_is_100_words(self) -> None:
        assert DEFAULT_MIN_UNIT_WORDS == 100

    def test_short_paragraphs_merge_into_one_unit(self) -> None:
        # 10 paragraphs of 8 words each (80 words total) stay under a 100-word target.
        text = "\n\n".join(f"Dies ist Satz Nummer {i} in diesem Testabsatz." for i in range(10))
        units = split_units(text)
        merged = merge_units(units, min_unit_words=100)
        assert len(merged) == 1
        assert merged[0].kind == "paragraph"
        assert merged[0].word_count == sum(u.word_count for u in units)

    def test_merging_stops_once_the_target_is_reached(self) -> None:
        # Each paragraph is 8 words; five of them clear a 30-word target, and merging
        # must not run past that into a sixth.
        paragraphs = [f"Absatz nummer {i} hat acht Woerter genau." for i in range(8)]
        units = split_units("\n\n".join(paragraphs))
        merged = merge_units(units, min_unit_words=30)
        assert merged[0].word_count >= 30
        assert merged[0].word_count < 30 + units[0].word_count, "must not overshoot by a whole extra paragraph"

    def test_headings_and_list_items_are_barriers(self) -> None:
        text = "Kurzer erster Satz hier drin.\n\nTitel Zwischendrin\n\nKurzer zweiter Satz auch hier."
        units = split_units(text)
        merged = merge_units(units, min_unit_words=100)
        assert [u.kind for u in merged] == ["paragraph", "heading", "paragraph"], (
            "merging must not cross the heading, even though neither side reaches 100 words alone"
        )

    def test_trailing_short_block_is_kept_as_its_own_unit(self) -> None:
        # 10 paragraphs of 8 words (80) clear an 80-word target exactly, so the buffer
        # flushes right before "Kurzer Rest." and the trailing block is that alone.
        text = "\n\n".join(f"Absatz Nummer {i} mit acht Woertern genau hier." for i in range(10)) + "\n\nKurzer Rest."
        units = split_units(text)
        merged = merge_units(units, min_unit_words=80)
        assert merged[-1].text == "Kurzer Rest."
        assert merged[-1].kind == "paragraph"
        assert merged[-1].word_count == 2

    def test_reindexes_in_document_order(self) -> None:
        text = "Titel\n\n" + "\n\n".join(f"Satz {i} hier drin heute." for i in range(6))
        units = split_units(text)
        merged = merge_units(units, min_unit_words=10)
        assert [u.index for u in merged] == list(range(len(merged)))

    def test_unscorable_reflects_the_analyzer_floor_not_the_merge_target(self) -> None:
        units = split_units("Kurzer Satz hier drin.")
        merged = merge_units(units, min_unit_words=100, min_words=3)
        assert merged[0].unscorable is False, "4 words clears the analyzer floor even far under the merge target"

    def test_merging_an_empty_list_is_empty(self) -> None:
        assert merge_units([]) == []

    def test_reassemble_accepts_merged_units(self) -> None:
        text = "\n\n".join(f"Satz Nummer {i} hier drin heute." for i in range(4))
        units = split_units(text)
        merged = merge_units(units, min_unit_words=10)
        assert reassemble(merged, {}) == text


class TestTextUnit:
    def test_units_are_immutable(self) -> None:
        unit = TextUnit(
            index=0,
            text="Ein Absatz mit genügend Wörtern.",
            start=0,
            end=32,
            kind="paragraph",
            word_count=5,
            unscorable=False,
        )
        assert unit.rewritable is True
        try:
            unit.text = "geändert"  # type: ignore[misc]
        except Exception as exp:
            assert isinstance(exp, (AttributeError, TypeError))
        else:  # pragma: no cover - would mean the dataclass stopped being frozen
            raise AssertionError("TextUnit must be frozen")

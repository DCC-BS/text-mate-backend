"""Unit tests for the AdvisorService source-resolution and dedup logic.

These cover the pure resolver methods directly (no LLM, no I/O). The service is
instantiated via ``__new__`` to bypass ``__init__`` (which loads rules files and
builds agents) — the methods under test use no instance state.
"""

from text_mate_backend.models.rule_models import DetectionViolation, ResolvedDetection, Rule, ViolationRange
from text_mate_backend.services.advisor import AdvisorService


def make_service() -> AdvisorService:
    return AdvisorService.__new__(AdvisorService)


def rule_lookup(rule_name: str) -> dict[str, Rule]:
    return {
        rule_name: Rule(
            name=rule_name,
            description="",
            file_name="doc.pdf",
            page_number=1,
            example="",
            collection="bundeskanzlei",
        )
    }


class TestFindSource:
    def test_exact_match_returns_first_occurrence(self) -> None:
        svc = make_service()
        text = "Die Uhrzeit 9:30 ist falsch. Auch 9:30 ist falsch."
        pos, length = svc._find_source("9:30", text)
        assert text[pos : pos + length] == "9:30"
        assert pos == text.find("9:30")

    def test_case_insensitive_match(self) -> None:
        svc = make_service()
        text = "Das Wort Beispiel steht hier."
        pos, length = svc._find_source("BEISPIEL", text)
        assert text[pos : pos + length].lower() == "beispiel"

    def test_not_found_returns_none(self) -> None:
        svc = make_service()
        assert svc._find_source("kommt nicht vor", "Ein kurzer Text.") is None

    def test_empty_consumed_equivalent_to_none(self) -> None:
        svc = make_service()
        text = "zweimal 9:30 und nochmal 9:30."
        assert svc._find_source("9:30", text, consumed=[]) == svc._find_source("9:30", text, consumed=None)

    def test_consumed_skips_to_next_occurrence(self) -> None:
        svc = make_service()
        text = "Die Anhörung beginnt um 9:30 Uhr. Die zweite Sitzung beginnt um 9:30 Uhr am folgenden Tag."
        first = text.find("9:30")
        second = text.find("9:30", first + 1)

        # With the first occurrence consumed, the second is returned.
        pos, length = svc._find_source("9:30", text, consumed=[(first, first + 4)])
        assert pos == second
        assert length == 4
        assert text[pos : pos + length] == "9:30"

    def test_consumed_two_occurrences_yields_third(self) -> None:
        svc = make_service()
        text = "a a a"
        first = text.find("a")
        second = text.find("a", first + 1)
        third = text.find("a", second + 1)

        pos, _ = svc._find_source("a", text, consumed=[(first, first + 1), (second, second + 1)])
        assert pos == third

    def test_consumed_all_returns_last_matchable(self) -> None:
        svc = make_service()
        text = "nur einmal kommt das wort vor"
        only = text.find("wort")
        # Every occurrence consumed — must not loop forever and returns a position.
        pos, _ = svc._find_source("wort", text, consumed=[(only, only + 4)])
        assert pos == only


class TestWhitespaceNormalizedSpan:
    def test_collapsed_whitespace_span_reflects_original(self) -> None:
        svc = make_service()
        # Source has a single space; the text has a double space. The exact and
        # case-insensitive finds miss, so the normalized path is used. The span
        # should cover the full double-space region in the original text.
        text = "xx  yy"
        normalized_text = svc._normalize_whitespace(text)
        assert normalized_text == "xx yy"  # sanity: double space collapsed

        found = svc._find_source_first("xx yy", text, 0)
        assert found is not None
        pos, length = found
        assert pos == 0
        assert length == len(text)  # the whole original span (6 chars) is covered


class TestResolveDetection:
    def test_two_identical_sources_resolve_to_distinct_ranges(self) -> None:
        svc = make_service()
        text = "Die Anhörung beginnt um 9:30 Uhr. Die zweite Sitzung beginnt um 9:30 Uhr am folgenden Tag."
        rule_name = "Uhrzeit mit Punkt in der 24-Stunden-Zählung"
        lookup = rule_lookup(rule_name)
        first = text.find("9:30")
        second = text.find("9:30", first + 1)

        v1 = DetectionViolation(rule_name=rule_name, reason="Punkt statt Schreibweise", source="9:30")
        r1 = svc._resolve_detection(v1, text, lookup, consumed_ranges=None)
        assert r1 is not None
        assert r1.range.start == first

        # Second resolution sees the first range as consumed.
        r2 = svc._resolve_detection(v1, text, lookup, consumed_ranges=[(r1.range.start, r1.range.end)])
        assert r2 is not None
        assert r2.range.start == second
        assert r2.range.start != r1.range.start

    def test_unlocatable_source_returns_none(self) -> None:
        svc = make_service()
        lookup = rule_lookup("x")
        v = DetectionViolation(rule_name="x", reason="r", source="gibt es nicht im text")
        assert svc._resolve_detection(v, "völlig anderer inhalt", lookup) is None

    def test_empty_source_returns_none(self) -> None:
        svc = make_service()
        lookup = rule_lookup("x")
        v = DetectionViolation(rule_name="x", reason="r", source="   ")
        assert svc._resolve_detection(v, "irgendein text", lookup) is None


class TestResolveAndDedup:
    def test_identical_repeated_violations_both_survive(self) -> None:
        """The core bug: two identical snippets must not collapse to one."""
        svc = make_service()
        text = "Die Anhörung beginnt um 9:30 Uhr. Die zweite Sitzung beginnt um 9:30 Uhr am folgenden Tag."
        rule_name = "Uhrzeit mit Punkt in der 24-Stunden-Zählung"
        lookup = rule_lookup(rule_name)

        violations = [
            DetectionViolation(rule_name=rule_name, reason="Punkt statt Schreibweise", source="9:30"),
            DetectionViolation(rule_name=rule_name, reason="Punkt statt Schreibweise", source="9:30"),
        ]
        survivors = svc._resolve_and_dedup(violations, text, lookup)
        assert len(survivors) == 2
        assert survivors[0].range.start != survivors[1].range.start
        assert {s.range.start for s in survivors} == {text.find("9:30"), text.find("9:30", text.find("9:30") + 1)}

    def test_genuine_duplicate_still_dropped(self) -> None:
        """Two different sources that overlap the same span collapse correctly."""
        svc = make_service()
        text = "Die Anhörung beginnt um 9:30 Uhr."
        rule_name = "Uhrzeit mit Punkt in der 24-Stunden-Zählung"
        lookup = rule_lookup(rule_name)
        # '9:30' and '9:30 Uhr' resolve to overlapping spans; the second is a dup.
        violations = [
            DetectionViolation(rule_name=rule_name, reason="r", source="9:30"),
            DetectionViolation(rule_name=rule_name, reason="r", source="9:30 Uhr"),
        ]
        survivors = svc._resolve_and_dedup(violations, text, lookup)
        assert len(survivors) == 1

    def test_distinct_rules_keep_separate(self) -> None:
        svc = make_service()
        text = "9:30 und gerade Anführungszeichen."
        lookup = {**rule_lookup("Uhrzeit"), **rule_lookup("Guillemets")}
        violations = [
            DetectionViolation(rule_name="Uhrzeit", reason="r", source="9:30"),
            DetectionViolation(rule_name="Guillemets", reason="r", source="gerade"),
        ]
        survivors = svc._resolve_and_dedup(violations, text, lookup)
        assert len(survivors) == 2
        assert {s.rule_name for s in survivors} == {"Uhrzeit", "Guillemets"}


class TestIsDuplicate:
    def _det(self, rule: str, start: int, end: int) -> ResolvedDetection:
        return ResolvedDetection(
            rule_name=rule,
            reason="",
            source="",
            range=ViolationRange(start=start, end=end),
            file_name="",
            page_number=0,
            collection="",
        )

    def test_overlapping_same_rule_is_duplicate(self) -> None:
        svc = make_service()
        seen = [self._det("r", 10, 20)]
        assert svc._is_duplicate(self._det("r", 15, 25), seen) is True

    def test_non_overlapping_same_rule_not_duplicate(self) -> None:
        svc = make_service()
        seen = [self._det("r", 10, 20)]
        assert svc._is_duplicate(self._det("r", 30, 40), seen) is False

    def test_same_start_is_duplicate(self) -> None:
        svc = make_service()
        seen = [self._det("r", 10, 20)]
        assert svc._is_duplicate(self._det("r", 10, 12), seen) is True

    def test_overlapping_different_rule_not_duplicate(self) -> None:
        svc = make_service()
        seen = [self._det("r1", 10, 20)]
        assert svc._is_duplicate(self._det("r2", 15, 25), seen) is False

    def test_empty_seen_not_duplicate(self) -> None:
        svc = make_service()
        assert svc._is_duplicate(self._det("r", 10, 20), []) is False


class TestOverlapsAny:
    def test_overlapping_range_found(self) -> None:
        assert AdvisorService._overlaps_any((10, 20), [(15, 25)]) is True

    def test_non_overlapping_not_found(self) -> None:
        assert AdvisorService._overlaps_any((10, 20), [(30, 40)]) is False

    def test_empty_ranges(self) -> None:
        assert AdvisorService._overlaps_any((10, 20), []) is False

    def test_adjacent_not_overlapping(self) -> None:
        assert AdvisorService._overlaps_any((10, 20), [(20, 30)]) is False


class TestMapNormalizedToOriginal:
    def test_identity_when_no_extra_whitespace(self) -> None:
        svc = make_service()
        text = "abc def"
        normalized = svc._normalize_whitespace(text)
        assert svc._map_normalized_to_original(text, normalized, 4) == 4  # 'd'

    def test_extra_whitespace_advances(self) -> None:
        svc = make_service()
        text = "abc  def"  # double space
        normalized = svc._normalize_whitespace(text)  # "abc def"
        # 'd' is at normalized index 4 but original index 5 (after double space).
        assert svc._map_normalized_to_original(text, normalized, 4) == 5


class TestToUtf16Offset:
    def test_bmp_text_unchanged(self) -> None:
        # All BMP (umlauts, ß) — UTF-16 code-unit count equals code-point count.
        assert AdvisorService._to_utf16_offset("Grüße Anhörung", 6) == 6

    def test_supplementary_char_before_offset_counts_double(self) -> None:
        # 🎉 (U+1F389) is one Python code point but two UTF-16 units.
        text = "🎉Anhörung"
        assert AdvisorService._to_utf16_offset(text, 1) == 2

    def test_supplementary_char_after_offset_ignored(self) -> None:
        text = "abc🎉"
        assert AdvisorService._to_utf16_offset(text, 3) == 3

    def test_mixed_offsets(self) -> None:
        text = "a🎉b🎉c"  # code points: a(0) 🎉(1) b(2) 🎉(3) c(4)
        assert AdvisorService._to_utf16_offset(text, 1) == 1  # "a"
        assert AdvisorService._to_utf16_offset(text, 3) == 4  # "a🎉b" -> 1+2+1
        assert AdvisorService._to_utf16_offset(text, 5) == 7  # whole string

    def test_zero_and_past_end(self) -> None:
        assert AdvisorService._to_utf16_offset("🎉abc", 0) == 0
        assert AdvisorService._to_utf16_offset("🎉abc", 4) == 5


class TestBuildViolationResultUtf16:
    def _resolved(self, text: str, snippet: str) -> ResolvedDetection:
        start = text.find(snippet)
        return ResolvedDetection(
            rule_name="r",
            reason="Grund",
            source=snippet,
            range=ViolationRange(start=start, end=start + len(snippet)),
            file_name="doc.pdf",
            page_number=1,
            collection="c",
        )

    def test_range_translated_to_utf16_with_emoji_before_match(self) -> None:
        svc = make_service()
        # "Anhörung" sits after an emoji; the emoji is 1 code point but 2 UTF-16
        # units, so the JS-visible offsets are each +1 versus the code points.
        text = "Test 🎉 Anhörung."
        resolved = self._resolved(text, "Anhörung")
        result = svc._build_violation_result(resolved, "Vorschlag", text)
        assert result.range.start == resolved.range.start + 1
        assert result.range.end == resolved.range.end + 1

    def test_bmp_only_range_unchanged(self) -> None:
        svc = make_service()
        text = "Grüße und Anhörung."
        resolved = self._resolved(text, "Anhörung")
        result = svc._build_violation_result(resolved, "Vorschlag", text)
        assert result.range.start == resolved.range.start
        assert result.range.end == resolved.range.end

    def test_source_and_other_fields_preserved(self) -> None:
        svc = make_service()
        text = "Test 🎉 Anhörung."
        resolved = self._resolved(text, "Anhörung")
        result = svc._build_violation_result(resolved, "Vorschlaß", text)
        assert result.source == "Anhörung"
        assert result.proposal == "Vorschlass"  # ß -> ss
        assert result.rule_name == resolved.rule_name
        assert result.reason == resolved.reason
        assert result.file_name == resolved.file_name
        assert result.page_number == resolved.page_number
        assert result.collection == resolved.collection

"""Tests for Canton Basel-Stadt house style guidelines."""

from text_mate_backend.agents.agent_types.quick_actions.condense_agent import CONDENSE_PROMPT
from text_mate_backend.agents.agent_types.quick_actions.medium_agent import (
    MAIL_PROMPT,
    OFFICIAL_LETTER_PROMPT,
    PRESENTATION_PROMPT,
    REPORT_PROMPT,
)
from text_mate_backend.utils.emails import EMAIL_PROMPT_TEMPLATE
from text_mate_backend.utils.house_style import BASEL_STADT_HOUSE_STYLE
from text_mate_backend.utils.offical_letter import OFFICIAL_LETTER_NOTICE


class TestBaselStadtHouseStyle:
    def test_anrede_und_ton_present(self) -> None:
        assert "«Sie»" in BASEL_STADT_HOUSE_STYLE
        assert "«wir»" in BASEL_STADT_HOUSE_STYLE
        assert "auf Augenhöhe" in BASEL_STADT_HOUSE_STYLE
        assert "Amtsdeutsch" in BASEL_STADT_HOUSE_STYLE

    def test_geschlechtergerechte_sprache_rules(self) -> None:
        assert "Paarformen" in BASEL_STADT_HOUSE_STYLE
        assert "Gendersternchen" in BASEL_STADT_HOUSE_STYLE
        assert "Bürger*innen" in BASEL_STADT_HOUSE_STYLE
        assert "Bürger·innen" in BASEL_STADT_HOUSE_STYLE
        assert "Bürger/-innen" in BASEL_STADT_HOUSE_STYLE
        assert "Kundendienst" in BASEL_STADT_HOUSE_STYLE

    def test_typografie_and_orthografie(self) -> None:
        assert "immer «ss», nie «ß»" in BASEL_STADT_HOUSE_STYLE
        assert BASEL_STADT_HOUSE_STYLE.count("ß") == 1
        assert "« »" in BASEL_STADT_HOUSE_STYLE
        assert "‹ ›" in BASEL_STADT_HOUSE_STYLE  # noqa: RUF001
        assert "„ “" in BASEL_STADT_HOUSE_STYLE  # As counter-example of what not to use

    def test_zahlen_daten_zeiten_betraege(self) -> None:
        assert "Fr. 327.65" in BASEL_STADT_HOUSE_STYLE
        assert "Fr. 20.–" in BASEL_STADT_HOUSE_STYLE  # noqa: RUF001
        assert "1. Januar 2022" in BASEL_STADT_HOUSE_STYLE
        assert "14 Uhr (NICHT 14.00 Uhr)" in BASEL_STADT_HOUSE_STYLE
        assert "044 123 45 67" in BASEL_STADT_HOUSE_STYLE
        assert "1 000 000" in BASEL_STADT_HOUSE_STYLE
        assert "«30%»" in BASEL_STADT_HOUSE_STYLE

    def test_fakten_treue(self) -> None:
        assert "Daten, Fristen, Namen, Beträge" in BASEL_STADT_HOUSE_STYLE
        assert "Identifikationszahlen" in BASEL_STADT_HOUSE_STYLE


class TestMediumPromptsComposition:
    def test_email_prompt_includes_house_style_and_email_rules(self) -> None:
        assert "# HAUSSTIL KANTON BASEL-STADT" in EMAIL_PROMPT_TEMPLATE
        assert "Betreff:" in EMAIL_PROMPT_TEMPLATE
        assert "Inhalt:" in EMAIL_PROMPT_TEMPLATE
        assert "Bildschirm-Lesbarkeit" in EMAIL_PROMPT_TEMPLATE
        assert "# HAUSSTIL KANTON BASEL-STADT" in MAIL_PROMPT

    def test_official_letter_includes_house_style_and_letter_rules(self) -> None:
        assert "# HAUSSTIL KANTON BASEL-STADT" in OFFICIAL_LETTER_NOTICE
        assert "Behördenbrief" in OFFICIAL_LETTER_NOTICE
        assert "Brückenschlag" in OFFICIAL_LETTER_NOTICE
        assert "# HAUSSTIL KANTON BASEL-STADT" in OFFICIAL_LETTER_PROMPT

    def test_presentation_and_report_prompts_include_house_style(self) -> None:
        assert "# HAUSSTIL KANTON BASEL-STADT" in PRESENTATION_PROMPT
        assert "Präsentationen" in PRESENTATION_PROMPT
        assert "Sprache des Ausgangstextes" in PRESENTATION_PROMPT
        assert "# HAUSSTIL KANTON BASEL-STADT" in REPORT_PROMPT
        assert "Management Summary" in REPORT_PROMPT
        assert "Sprache des Ausgangstextes" in REPORT_PROMPT

    def test_condense_prompt_includes_house_style(self) -> None:
        assert "# HAUSSTIL KANTON BASEL-STADT" in CONDENSE_PROMPT
        assert "verdichten" in CONDENSE_PROMPT
        assert "roten Faden" in CONDENSE_PROMPT
        assert "Füllstoff" in CONDENSE_PROMPT
        assert "Sprache des Ausgangstextes" in CONDENSE_PROMPT

    def test_house_style_and_templates_include_language_retention(self) -> None:
        assert "Sprache des Ausgangstextes" in BASEL_STADT_HOUSE_STYLE
        assert "Sprache des Ausgangstextes" in EMAIL_PROMPT_TEMPLATE
        assert "Sprache des Ausgangstextes" in OFFICIAL_LETTER_NOTICE

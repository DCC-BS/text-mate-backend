"""Tests for Canton Basel-Stadt house style guidelines."""

from text_mate_backend.utils.house_style import BASEL_STADT_HOUSE_STYLE


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
        assert "‹ ›" in BASEL_STADT_HOUSE_STYLE
        assert "„ “" in BASEL_STADT_HOUSE_STYLE  # As counter-example of what not to use

    def test_zahlen_daten_zeiten_betraege(self) -> None:
        assert "Fr. 327.65" in BASEL_STADT_HOUSE_STYLE
        assert "Fr. 20.–" in BASEL_STADT_HOUSE_STYLE
        assert "1. Januar 2022" in BASEL_STADT_HOUSE_STYLE
        assert "14 Uhr (NICHT 14.00 Uhr)" in BASEL_STADT_HOUSE_STYLE
        assert "044 123 45 67" in BASEL_STADT_HOUSE_STYLE
        assert "1 000 000" in BASEL_STADT_HOUSE_STYLE
        assert "«30%»" in BASEL_STADT_HOUSE_STYLE

    def test_fakten_treue(self) -> None:
        assert "Daten, Fristen, Namen, Beträge" in BASEL_STADT_HOUSE_STYLE
        assert "Identifikationszahlen" in BASEL_STADT_HOUSE_STYLE

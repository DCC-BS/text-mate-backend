# Canton Basel-Stadt House Style Improvements Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Upgrade `BASEL_STADT_HOUSE_STYLE` with the complete, reconciled Basel-Stadt rules (typography, currency, times, dates, phone numbers, gendering, active voice) and align medium-specific quick action prompts (`emails.py`, `offical_letter.py`, `medium_agent.py`) with clean prompt engineering practices.

**Architecture:** Enrich `BASEL_STADT_HOUSE_STYLE` as the single canonical house style constant in `utils/house_style.py`, deduplicate medium prompt templates in `utils/emails.py` and `utils/offical_letter.py` so they focus on structure, wire all medium options in `medium_agent.py` to inherit the house style cleanly, and provide comprehensive unit tests in `tests/test_house_style.py`.

**Tech Stack:** Python 3.13, PydanticAI, Pytest

## Global Constraints

- Swiss orthography: always «ss», never «ß» (except within the prohibition rule itself).
- Typography: French guillemets (« ») and half-guillemets (‹ ›), never German quotation marks („ “).
- Currency: `Fr.` before the amount, dash for missing rappen (`Fr. 20.–`), no CHF unless referencing foreign code.
- Gendering: Pair forms or gender-neutral nouns; strict ban on `*`, `:`, `_`, `·`, Binnen-I, `()`, and `/-innen`.
- Dates & Times: Full month names (`1. Januar 2022`), 24h format with period (`9.25 Uhr`, `14 Uhr`).
- Phone numbers: grouped `044 123 45 67`.
- All tests in `tests/` must pass without regressions.

---

### Task 1: Create Unit Tests for `BASEL_STADT_HOUSE_STYLE`

**Files:**
- Create: `tests/test_house_style.py`
- Modify: `src/text_mate_backend/utils/house_style.py`
- Test: `tests/test_house_style.py`

**Interfaces:**
- Consumes: `text_mate_backend.utils.house_style.BASEL_STADT_HOUSE_STYLE` (str)
- Produces: Test suite validating all required sections, prohibition lists, and formatting rules.

- [ ] **Step 1: Write the failing test**

```python
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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_house_style.py -v`
Expected: FAIL (missing new typography, currency, dates, and number rules in current `BASEL_STADT_HOUSE_STYLE`)

- [ ] **Step 3: Update `BASEL_STADT_HOUSE_STYLE` in `src/text_mate_backend/utils/house_style.py`**

```python
# Hausstil der Verwaltung Kanton Basel-Stadt.
# Abgeleitet aus den amtlichen Leitfäden in assets/docs/
# (Merkblatt Behördenbriefe, Rechtschreibleitfaden, Leitfaden geschlechtergerechte
# Sprache, Empfehlungen Anglizismen) und abgestimmt mit utils/simplify_style.py.
# Wird von den Brief-, E-Mail-, Präsentations- und Berichts-Prompts wiederverwendet.

# ruff: noqa: E501  # Line too long - German language rules and prompts need to be preserved exactly

BASEL_STADT_HOUSE_STYLE = """
# HAUSSTIL KANTON BASEL-STADT
Beachte beim Schreiben immer die folgenden Regeln der Verwaltung Kanton Basel-Stadt:

1. Ton, Anrede und Haltung:
   - Sprich die Leserin oder den Leser direkt mit «Sie» an. «Sie», «Ihr» und «Ihnen» schreibst du immer gross.
   - Schreibe persönlich: «wir» für die Verwaltung, «Sie» für die angeschriebene Person. Verstecke dich nicht hinter «die Behörde», «es wird» oder anderen unpersönlichen Formen.
   - Schreibe respektvoll und auf Augenhöhe, nie von oben herab, nie drohend oder misstrauisch.
   - Bitte und danke dort, wo es angebracht ist. Formuliere Aufforderungen nicht rein befehlend.
   - Vermeide Amtsdeutsch, Kanzleistil und Floskeln. Schreibe natürlich und verständlich (statt «Zur Beantwortung steht Ihnen ... zur Verfügung» besser «Rufen Sie uns an, wenn Sie Fragen haben»; statt «in Kenntnis setzen» besser «mitteilen», statt «in Abzug bringen» besser «abziehen»).

2. Satzbau und Verständlichkeit:
   - Nutze kurze, klare Sätze im Aktiv. Ein Gedanke pro Satz.
   - Entflechte Schachtelsätze. Aus einem langen Satz dürfen mehrere kurze werden.
   - Formuliere grundsätzlich positiv und bejahend.
   - Vermeide Substantivierungen. Verwende stattdessen Verben und Adjektive.

3. Geschlechtergerechte Sprache:
   - Verwende nie die alleinige männliche Form für Personen unbekannten oder gemischten Geschlechts.
   - Verwende Paarformen («Bürgerinnen und Bürger», «die Mitarbeiterin oder der Mitarbeiter») oder geschlechtsneutrale Formen («die Stimmberechtigten», «die Fachperson», «die Belegschaft»).
   - Verwende NIE Gendersternchen, Doppelpunkt, Unterstrich, Mediopunkt, Binnen-I, Klammerform oder Schrägstrich-Sparschreibung (also nicht «Bürger*innen», «Bürger:innen», «Bürger_innen», «Bürger·innen», «BürgerInnen», «Bürger(innen)», «Bürger/-innen»).
   - Verwende keine Paarform im ersten Teil eines zusammengesetzten Wortes (nicht «Kundinnen- und Kundendienst», sondern «Kundendienst»).
   - Behalte die einmal gewählte Reihenfolge der Paarform im ganzen Text bei.
   - Verbinde die Paarform in der Einzahl mit «oder», in der Mehrzahl mit «und», nie mit «beziehungsweise».
   - Juristische Personen und Organisationseinheiten bezeichnest du mit nur einer Form.

4. Schweizer Rechtschreibung und Typografie:
   - Verwende Schweizer Rechtschreibung: immer «ss», nie «ß».
   - Verwende immer französische Anführungszeichen (« ») anstelle von deutschen Anführungszeichen („ “). Für ein Zitat innerhalb eines Zitats verwendest du die halben Guillemets (‹ ›).
   - Besteht eine Zusammensetzung aus vier oder mehr Sinneinheiten, gliederst du sie mit einem Bindestrich, ohne eine Sinneinheit auseinanderzureissen: «Motorfahrzeug-Ausweispflicht», «Rheinschifffahrtspolizei-Verordnung». Kurze Zusammensetzungen aus zwei oder drei Teilen schreibst du ohne Bindestrich.
   - Vermeide Abkürzungen für Wörter. Schreibe sie aus: «zum Beispiel» statt «z. B.», «das heisst» statt «d. h.», «und so weiter» statt «usw.». Verwendest du eine mehrgliedrige Abkürzung ausnahmsweise doch, setzt du ein Leerzeichen zwischen ihre Bestandteile: «z. B.», «d. h.».
   - Wähle eine Schreibvariante und verwende sie im ganzen Text einheitlich.

5. Zahlen, Daten, Zeiten und Beträge:
   - Zahlen bis zwölf schreibst du aus, ebenso runde Zahlwörter wie zwanzig, hundert, tausend. Ab 13 verwendest du Ziffern.
   - Fristen, Geldbeträge und physikalische Grössen schreibst du immer in Ziffern.
   - Zahlen, die zusammengehören oder einander gegenübergestellt werden, schreibst du in Ziffern: «Die Frist beträgt 7 Tage, bei Verträgen 14 Tage».
   - Prozentangaben schreibst du als Ziffer direkt gefolgt vom Prozentzeichen, ohne Leerzeichen: «30%». Mass- und Gewichtsangaben schreibst du als Ziffer mit einem Leerzeichen vor der Einheit: «5 t», «10 m», «2 Tonnen».
   - Grosse Zahlen ab 5 Stellen gliederst du in Dreiergruppen mit Leerzeichen: 1 000 000. Vierstellige Zahlen bleiben ungegliedert. Apostroph, Punkt und Komma verwendest du dafür NIE.
   - Bei einem genau bezifferten Geldbetrag verwendest du als Währungseinheit «Fr.» und schreibst sie mit Leerzeichen VOR den Betrag: Fr. 327.65, Fr. 12.50, Fr. 40.50. Die Einheit steht nie hinter dem Betrag (NICHT 40.50 Fr.). Im Fliesstext ohne genaue Ziffer schreibst du «Franken» aus: 20 Franken, 50 000 Franken; ein Beispiel: aus «40.50 Franken» wird «Fr. 40.50» (NICHT 40.50 Franken). Andere Währungen behandelst du gleich: EUR 14.90.
   - Franken und Rappen trennst du mit einem Punkt, nie mit einem Komma. Fehlen die Rappen, setzt du an ihrer Stelle einen Gedankenstrich: Fr. 20.– (NICHT Fr. 20.00, NICHT Fr. 20,–).
   - Formatiere Datumsangaben immer so: 1. Januar 2022, 15. Februar 2022. Den Monatsnamen schreibst du immer aus, nie als Ziffer.
   - Jahreszahlen schreibst du immer vierstellig aus: 2022, 2025-2030.
   - Formatiere Zeitangaben in der 24-Stunden-Zählung und trenne Stunden und Minuten mit einem Punkt, nie mit einem Doppelpunkt: 9.25 Uhr, 15.45 Uhr, 20.15 Uhr. Volle Stunden schreibst du ohne Minutenangabe: 14 Uhr (NICHT 14.00 Uhr).
   - Gliedere inländische Telefonnummern so: die Vorwahl als Dreierblock mit führender Null, die übrigen Ziffern in Zweierblöcken, getrennt durch Leerzeichen: 044 123 45 67. Schrägstriche und Klammern um die Vorwahl verwendest du NIE.

6. Anglizismen:
   - Verwende nur etablierte Anglizismen (z. B. «E-Mail», «Computer», «Leasing»).
   - Ersetze unnötige Anglizismen durch deutsche Wörter («Sitzung» statt «Meeting», «Veranstaltung» statt «Event»).
   - Erkläre unklare Fachbegriffe bei der ersten Verwendung. Verwende keinen Jugend- oder Werbeslang.

7. Fakten:
   - Übernimm alle Fakten (Daten, Fristen, Namen, Beträge, Bedingungen, Pflichten) exakt und unverändert.
   - Identifikationszahlen übernimmst du 1:1: Stammnummer 123.456.789, AHV-Nummer 756.1234.5678.90, Konto 01-100101-9.
   - Erfinde nichts dazu. Schreibe nur, was im Ausgangstext steht.
""".strip()
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_house_style.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/text_mate_backend/utils/house_style.py tests/test_house_style.py
git commit -m "feat(house_style): upgrade BASEL_STADT_HOUSE_STYLE with reconciled standards"
```

---

### Task 2: Refactor `emails.py` and `offical_letter.py` Prompts

**Files:**
- Modify: `src/text_mate_backend/utils/emails.py`
- Modify: `src/text_mate_backend/utils/offical_letter.py`
- Test: `tests/test_house_style.py`

**Interfaces:**
- Consumes: `BASEL_STADT_HOUSE_STYLE` from `text_mate_backend.utils.house_style`
- Produces: Cleanly structured `EMAIL_PROMPT_TEMPLATE` and `OFFICIAL_LETTER_NOTICE` focused on medium conventions without redundant generic style text.

- [ ] **Step 1: Write test for email and official letter prompt composition**

Add to `tests/test_house_style.py`:
```python
from text_mate_backend.utils.emails import EMAIL_PROMPT_TEMPLATE
from text_mate_backend.utils.offical_letter import OFFICIAL_LETTER_NOTICE


class TestMediumPromptsComposition:
    def test_email_prompt_includes_house_style_and_email_rules(self) -> None:
        assert "# HAUSSTIL KANTON BASEL-STADT" in EMAIL_PROMPT_TEMPLATE
        assert "Betreff:" in EMAIL_PROMPT_TEMPLATE
        assert "Inhalt:" in EMAIL_PROMPT_TEMPLATE
        assert "Bildschirm-Lesbarkeit" in EMAIL_PROMPT_TEMPLATE

    def test_official_letter_includes_house_style_and_letter_rules(self) -> None:
        assert "# HAUSSTIL KANTON BASEL-STADT" in OFFICIAL_LETTER_NOTICE
        assert "Behördenbrief" in OFFICIAL_LETTER_NOTICE
        assert "Brückenschlag" in OFFICIAL_LETTER_NOTICE
```

- [ ] **Step 2: Run test to verify status**

Run: `uv run pytest tests/test_house_style.py -v`

- [ ] **Step 3: Refactor `src/text_mate_backend/utils/emails.py` and `src/text_mate_backend/utils/offical_letter.py`**

In `src/text_mate_backend/utils/emails.py`:
```python
# from https://www.bk.admin.ch/bk/de/home/dokumentation/sprachen/hilfsmittel-textredaktion/merkblatt-behoerdenbriefe.html

from text_mate_backend.utils.house_style import BASEL_STADT_HOUSE_STYLE

EMAIL_PROMPT_TEMPLATE = (
    """
# ROLLE
Du bist ein Kommunikationsassistent für digitale Behördenkommunikation der Verwaltung Kanton Basel-Stadt. Du optimierst E-Mail-Entwürfe so, dass sie effizient, freundlich und am Bildschirm leicht lesbar sind.

# ZIEL
Die E-Mail muss schnell erfassbar sein, Missverständnisse vermeiden und darf niemals emotional eskalieren.

# INSTRUKTIONEN ZUR E-MAIL-GESTALTUNG

1. Betreffzeile:
   - Formuliere einen präzisen, aussagekräftigen Betreff. Die empfangende Person muss sofort wissen, worum es geht und ob Handlungsbedarf besteht.

2. Bildschirm-Lesbarkeit:
   - Fasse dich kurz («KISS-Prinzip»).
   - Nutze kurze Absätze (max. 2-3 Sätze) und viel Weissraum.
   - Verwende Aufzählungszeichen (Bullet Points) für Listen oder Schritte.

3. Tonalität & Deeskalation:
   - E-Mails wirken oft kühler als Briefe. Schreibe daher bewusst freundlich und verbindlich.
   - Vermeide emotionale Reaktionen oder Ironie. Bleibe sachlich und lösungsorientiert.

4. Handlungsaufforderung (Call to Action):
   - Mache am Ende deutlich, was der nächste Schritt ist: wer tut was bis wann.
   - Falls Anhänge erwähnt werden: Stelle sicher, dass im Text darauf hingewiesen wird (z. B. «Im Anhang finden Sie...»).

# FORMATIERUNG
Gib die E-Mail in folgendem Format aus:
Betreff: [Optimierter Betreff]
Inhalt: [Optimierter E-Mail-Text]

"""
    + BASEL_STADT_HOUSE_STYLE
)
```

In `src/text_mate_backend/utils/offical_letter.py`:
```python
# from https://www.bk.admin.ch/bk/de/home/dokumentation/sprachen/hilfsmittel-textredaktion/merkblatt-behoerdenbriefe.html

from text_mate_backend.utils.house_style import BASEL_STADT_HOUSE_STYLE

OFFICIAL_LETTER_NOTICE = (
    """
# ROLLE
Du bist ein Experte für moderne, bürgernahe Verwaltungskommunikation der Verwaltung Kanton Basel-Stadt. Deine Aufgabe ist es, einen Entwurf für einen Behördenbrief in einen optimierten Text umzuwandeln, der den Grundsätzen «Persönlich, Sachgerecht, Verständlich» folgt.

# ZIEL
Der Brief soll als «Brückenschlag» dienen. Er soll den Bürgerinnen und Bürgern auf Augenhöhe begegnen, Vertrauen schaffen und Missverständnisse vermeiden, ohne die rechtliche Korrektheit zu verlieren.

# INSTRUKTIONEN ZUM BEHÖRDENBRIEF

1. Persönlich (WEM schreibe ich?):
   - Versetze dich in die Lage der empfangenden Person. Schreibe empathisch und respektvoll.
   - Vermeide bürokratische Arroganz («Von oben herab»).
   - Entschuldige dich für Fehler der Behörde, falls im Entwurf erwähnt.

2. Sachgerecht (WAS schreibe ich?):
   - Filtere Unnötiges heraus. Konzentriere dich auf den Kern der Sache.
   - Gehe konkret auf die Fragen und Anliegen ein (keine unpassenden Standardtextbausteine).
   - Gib klare Handlungsanweisungen: Wer muss was bis wann tun?
   - Erkläre verständlich die Konsequenzen von Handlungen oder Unterlassungen.

3. Aufbau (WIE strukturiere ich?):
   - Folge einem klaren roten Faden.
   - Nutze sinnvolle Absätze und prägnante Zwischenüberschriften, um längere Texte zu gliedern.

# FORMATIERUNG
- Der Output soll ein fertig strukturierter Brieftext sein (Betreff, Anrede, Textkörper, Grussformel).
- Verwende kein HTML.
"""
    + BASEL_STADT_HOUSE_STYLE
)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_house_style.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/text_mate_backend/utils/emails.py src/text_mate_backend/utils/offical_letter.py tests/test_house_style.py
git commit -m "refactor(quick_actions): deduplicate and align email and letter prompts with house style"
```

---

### Task 3: Align `MediumAgent` Prompts (`presentation`, `report`) and Prompt Framing

**Files:**
- Modify: `src/text_mate_backend/agents/agent_types/quick_actions/medium_agent.py`
- Test: `tests/test_quick_action_router.py`

**Interfaces:**
- Consumes: `BASEL_STADT_HOUSE_STYLE` from `text_mate_backend.utils.house_style`
- Produces: Updated `MediumAgent` where all options (`email`, `official_letter`, `presentation`, `report`) leverage house styles and structured instructions.

- [ ] **Step 1: Update `MediumAgent` in `src/text_mate_backend/agents/agent_types/quick_actions/medium_agent.py`**

Include `BASEL_STADT_HOUSE_STYLE` in `PRESENTATION_PROMPT` and `REPORT_PROMPT`:
```python
from text_mate_backend.utils.house_style import BASEL_STADT_HOUSE_STYLE

PRESENTATION_PROMPT = (
    """
Du bist ein Assistent der Verwaltung Kanton Basel-Stadt, der beim Schreiben von Präsentationen hilft.
Beginne mit einer fesselnden Einleitung, die die Aufmerksamkeit des Publikums weckt,
gefolgt von einer Reihe gut strukturierter Punkte, die das Hauptthema stützen.
Schliesse mit einer starken Schlussaussage, die die Kernbotschaft verstärkt.
"""
    + BASEL_STADT_HOUSE_STYLE
)

REPORT_PROMPT = (
    """
Du bist ein Assistent der Verwaltung Kanton Basel-Stadt, der beim Schreiben von Berichten hilft.
Beginne mit einer Management Summary, die Zweck und Ergebnisse des Berichts überblicksartig darstellt,
gefolgt von ausführlichen Abschnitten mit Daten und Analyse.
Schliesse mit einem Fazit, das die wichtigsten Erkenntnisse und Empfehlungen zusammenfasst.
"""
    + BASEL_STADT_HOUSE_STYLE
)
```

- [ ] **Step 2: Run quick action router tests**

Run: `uv run pytest tests/test_quick_action_router.py -v`
Expected: PASS

- [ ] **Step 3: Run entire test suite to ensure full regression-free execution**

Run: `uv run pytest -v`
Expected: PASS (all 476+ tests passing)

- [ ] **Step 4: Commit**

```bash
git add src/text_mate_backend/agents/agent_types/quick_actions/medium_agent.py
git commit -m "feat(medium_agent): include house style in presentation and report prompts"
```

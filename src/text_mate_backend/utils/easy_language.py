"""Easy Language (Einfache Sprache) prompt content.

This module provides the prompt, rules, and system message for converting complex German
texts into "Einfache Sprache" (ES, language level B1-A2). It previously also carried
"Leichte Sprache" (LS) and OpenAI-provider constants; both were dead code (unreferenced
outside this module) and have been removed — see ``docs/simplify_rules_audit.md`` for what
was deleted and why. Only the Claude/Einfache-Sprache path is live.

The prompts and rules are derived from the Canton of Zurich administration guidelines.
While these are good defaults based on testing, we strongly recommend validating and
adjusting these rules to your organization's specific needs.

``RULES_ES`` has been **reconciled with the Basel-Stadt / Bundeskanzlei rule set** that
this project's advisor enforces (``assets/docs/rules/bundeskanzlei.json``,
``assets/docs/rules/merkblatt_behoerdenbriefe.json``, ``utils/house_style.py``). Where the
Zurich guidelines contradicted those rules — units and percent signs, full hours,
gendering forms, currency form — the Bundeskanzlei formulation won (and, for currency, was
itself corrected once against actual Basel-Stadt practice). Every bullet, its verdict and
the rule that overrode it are documented in ``docs/simplify_rules_audit.md``; change a rule
here only together with that table.

References:
- https://www.zh.ch/de/webangebote-entwickeln-und-gestalten/inhalt/inhalte-gestalten/informationen-bereitstellen/umgang-mit-sprache.html
- https://www.zh.ch/de/webangebote-entwickeln-und-gestalten/inhalt/barrierefreiheit/regeln-fuer-leichte-sprache.html
- https://www.zh.ch/content/dam/zhweb/bilder-dokumente/themen/politik-staat/teilhabe/erfolgsbeispiele-teilhabe/Sprachleitfaden_Strassenverkehrsamt_Maerz_2022.pdf

Note: Anthropic recommends putting content first and prompt last, which is opposite to
OpenAI's usual prompt structure. Claude models prefer XML tags while OpenAI models
prefer Markdown or JSON. We use Claude's prompt structure for Mistral with good success.
"""
# ruff: noqa: E501  # Line too long - German language rules and prompts need to be preserved exactly

from __future__ import annotations

# ========================================================================s=====
# SYSTEM MESSAGES
# =============================================================================

SYSTEM_MESSAGE_ES: str = (
    "Du bist ein hilfreicher Assistent, der Texte in Einfache Sprache, Sprachniveau B1 bis A2, "
    "umschreibt. Sei immer wahrheitsgemäss und objektiv. Schreibe nur das, was du sicher aus dem "
    "Text des Benutzers weisst. Arbeite die Texte immer vollständig durch und kürze nicht. "
    "Mache keine Annahmen. Schreibe einfach und klar und immer in deutscher Sprache. "
)

# =============================================================================
# LANGUAGE RULES
# =============================================================================


RULES_ES = """
- Schreibe kurze Sätze mit höchstens 12 Wörtern.
- Beschränke dich auf eine Aussage, einen Gedanken pro Satz.
- Verwende aktive Sprache anstelle von Passiv.
- Formuliere grundsätzlich positiv und bejahend.
- Strukturiere den Text übersichtlich mit kurzen Absätzen.
- Verwende einfache, kurze, häufig gebräuchliche Wörter.
- Wenn zwei Wörter dasselbe bedeuten, verwende das kürzere und einfachere Wort.
- Vermeide Füllwörter und unnötige Wiederholungen.
- Erkläre Fachbegriffe und Fremdwörter.
- Schreibe immer einfach, direkt und klar. Vermeide komplizierte Konstruktionen und veraltete Begriffe. Vermeide «Behördendeutsch».
- Benenne Gleiches immer gleich. Verwende für denselben Begriff, Gegenstand oder Sachverhalt immer dieselbe Bezeichnung. Wiederholungen von Begriffen sind in Texten in Einfacher Sprache normal.
- Vermeide Substantivierungen. Verwende stattdessen Verben und Adjektive.
- Vermeide Adjektive und Adverbien, wenn sie nicht unbedingt notwendig sind.
- Besteht eine Zusammensetzung aus vier oder mehr Sinneinheiten, gliederst du sie mit einem Bindestrich, ohne eine Sinneinheit auseinanderzureissen. Beispiele: «Motorfahrzeug-Ausweispflicht», «Rheinschifffahrtspolizei-Verordnung». Kurze Zusammensetzungen aus zwei oder drei Teilen schreibst du ohne Bindestrich.
- Schreibe geschlechtergerecht. Verwende Paarformen («Bürgerinnen und Bürger», «die Mitarbeiterin oder der Mitarbeiter») oder geschlechtsneutrale Formen («die Stimmberechtigten», «die Fachperson»). Verwende NIE Gendersternchen, Doppelpunkt, Unterstrich, Mediopunkt, Binnen-I, Klammerform oder Schrägstrich-Sparschreibung, also nicht «Bürger*innen», «Bürger:innen», «Bürger_innen», «BürgerInnen», «Bürger(innen)», «Bürger/-innen». Im ersten Teil eines zusammengesetzten Wortes verwendest du keine Paarform: «Kundendienst», nicht «Kundinnen- und Kundendienst». Behalte die einmal gewählte Reihenfolge der Paarform im ganzen Text bei. Verbinde die Paarform in der Einzahl mit «oder» und in der Mehrzahl mit «und», nie mit «beziehungsweise».
- Vermeide Abkürzungen für Wörter. Schreibe sie aus. Z.B. «zum Beispiel» statt «z. B.», «das heisst» statt «d. h.», «und so weiter» statt «usw.», «10 Millionen» statt «10 Mio.». Wenn du eine mehrgliedrige Abkürzung ausnahmsweise doch verwendest, setzt du zwischen ihre Bestandteile ein Leerzeichen: «z. B.», «d. h.».
- Prozentangaben schreibst du als Ziffer direkt gefolgt vom Prozentzeichen, ohne Leerzeichen: «30%». Mass- und Gewichtsangaben schreibst du als Ziffer mit einem Leerzeichen vor der Einheit: «5 t», «10 m», «2 Tonnen». Für gebräuchliche Einheiten wie Meter (m), Kilometer (km), Gramm (g), Kilogramm (kg), Liter (l) oder Milliliter (ml) verwendest du die Abkürzung; alle anderen Einheiten schreibst du aus. Ein ausgeschriebenes Zahlwort vor einer abgekürzten Einheit ist falsch («zwölf km»).
- Verwende immer französische Anführungszeichen (« ») anstelle von deutschen Anführungszeichen („ “). Für ein Zitat innerhalb eines Zitats verwendest du die halben Guillemets (‹ ›).
- Gliedere inländische Telefonnummern so: die Vorwahl als Dreierblock mit führender Null, die übrigen Ziffern in Zweierblöcken, getrennt durch Leerzeichen. Beispiel: 044 123 45 67. Den alten Stil mit Schrägstrich (044/123 45 67) und die Vorwahl in Klammern verwendest du NIE.
- Formatiere Datumsangaben immer so: 1. Januar 2022, 15. Februar 2022. Den Monatsnamen schreibst du immer aus, nie als Ziffer (NICHT 2.9.2006).
- Jahreszahlen schreibst du immer vierstellig aus: 2022, 2025-2030.
- Formatiere Zeitangaben in der 24-Stunden-Zählung und trenne Stunden und Minuten mit einem Punkt. Verwende NIE einen Doppelpunkt. Volle Stunden schreibst du ohne Minutenangabe. Beispiele: 9.25 Uhr (NICHT 9:25), 15.45 Uhr, 20.15 Uhr, 22.30 Uhr, 14 Uhr (NICHT 14.00 Uhr), 8 Uhr (NICHT 8.00 Uhr).
- Zahlen bis zwölf schreibst du aus, ebenso runde Zahlwörter wie zwanzig, hundert, tausend. Ab 13 verwendest du Ziffern.
- Fristen, Geldbeträge und physikalische Grössen schreibst du immer in Ziffern.
- Zahlen, die zusammengehören oder einander gegenübergestellt werden, schreibst du immer in Ziffern. Beispiele: 5-10, 20 oder 30; «Die Frist beträgt 7 Tage, bei Verträgen 14 Tage».
- Grosse Zahlen ab 5 Stellen gliederst du in Dreiergruppen mit Leerzeichen. Beispiel: 1 000 000. Vierstellige Zahlen bleiben ungegliedert. Punkt, Komma oder Apostroph verwendest du dafür NIE (NICHT 1'000'000, NICHT 1.000.000).
- Achtung: Identifikationszahlen übernimmst du 1:1. Beispiel: Stammnummer 123.456.789, AHV-Nummer 756.1234.5678.90, Konto 01-100101-9.
- Ausserhalb von Geldbeträgen ist das Komma das deutsche Dezimalzeichen. Überflüssige Nullen nach dem Komma schreibst du nicht. Beispiel: 5,5 Millionen, 3,75 %, 2,25 Stunden.
- Bei einem genau bezifferten Geldbetrag verwendest du als Währungseinheit «Fr.» und schreibst sie mit Leerzeichen VOR den Betrag: Fr. 327.65, Fr. 12.50, Fr. 40.50. Die Einheit steht nie hinter dem Betrag (NICHT 40.50 Fr.). Im Fliesstext ohne genaue Ziffer schreibst du «Franken» aus: 20 Franken, 50 000 Franken; ein Beispiel: aus «40.50 Franken» wird «Fr. 40.50» (NICHT 40.50 Franken). Andere Währungen behandelst du gleich: EUR 14.90.
- Franken und Rappen trennst du mit einem Punkt, nie mit einem Komma. Fehlen die Rappen, setzt du an ihrer Stelle einen Gedankenstrich: Fr. 20.– (NICHT Fr. 20.00, NICHT Fr. 20,–). Bei grossen, gerundeten Beträgen gilt wieder das Dezimalkomma: Fr. 45,2 Millionen.
- Die Anrede mit «Sie», «Ihr» und «Ihnen» schreibst du immer gross. Beispiel: «Sie haben», «Ihr Gesuch».
""".strip()


REWRITE_COMPLETE = """- Achte immer sehr genau darauf, dass ALLE Informationen aus dem schwer verständlichen Text in deinem verständlicheren Text enthalten sind. Kürze niemals Informationen. Wo sinnvoll kannst du zusätzliche Beispiele hinzufügen, um den Text verständlicher zu machen und relevante Inhalte zu konkretisieren."""


# =============================================================================
# CLAUDE TEMPLATES
# =============================================================================

# Claude template for "Einfache Sprache" (Simple Language)
CLAUDE_TEMPLATE_ES: str = """
Hier ist ein schwer verständlicher Text, den du vollständig in Einfache Sprache, Sprachniveau B1 bis A2, umschreiben sollst:

<schwer-verständlicher-text>
{prompt}
</schwer-verständlicher-text>

Bitte lies den Text sorgfältig durch und schreibe ihn vollständig in Einfache Sprache um.

Beachte dabei folgende Regeln:

{completeness}
{rules}

Formuliere den Text jetzt in Einfache Sprache, Sprachniveau B1 bis A2, um.
""".strip()

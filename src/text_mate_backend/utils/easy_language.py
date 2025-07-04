"""Easy Language (Einfache Sprache) and Plain Language (Leichte Sprache) utilities.

This module provides prompts, rules, and templates for converting complex German texts
into "Einfache Sprache" (ES, language level B1-A2) and "Leichte Sprache" (LS, language level A2-A1).

The prompts and rules are derived from the Canton of Zurich administration guidelines.
While these are good defaults based on testing, we strongly recommend validating and
adjusting these rules to your organization's specific needs.

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
    "umschreibt. Sei immer wahrheitsgemäß und objektiv. Schreibe nur das, was du sicher aus dem "
    "Text des Benutzers weisst. Arbeite die Texte immer vollständig durch und kürze nicht. "
    "Mache keine Annahmen. Schreibe einfach und klar und immer in deutscher Sprache. "
    "Gib dein Ergebnis innerhalb von <einfachesprache> Tags aus."
)

SYSTEM_MESSAGE_LS: str = (
    "Du bist ein hilfreicher Assistent, der Texte in Leichte Sprache, Sprachniveau A2 bis A1, "
    "umschreibt. Sei immer wahrheitsgemäß und objektiv. Schreibe nur das, was du sicher aus dem "
    "Text des Benutzers weisst. Arbeite die Texte immer vollständig durch und kürze nicht. "
    "Mache keine Annahmen. Schreibe einfach und klar und immer in deutscher Sprache. "
    "Gib dein Ergebnis innerhalb von <leichtesprache> Tags aus."
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
- Wenn du vier oder mehr Wörter zusammensetzt, setzt du Bindestriche. Beispiel: «Motorfahrzeug-Ausweispflicht».
- Achte auf die sprachliche Gleichbehandlung von Mann und Frau. Verwende immer beide Geschlechter oder schreibe geschlechtsneutral.
- Vermeide Abkürzungen grundsätzlich. Schreibe stattdessen die Wörter aus. Z.B. «10 Millionen» statt «10 Mio.», «200 Kilometer pro Stunde» statt «200 km/h», «zum Beispiel» statt «z.B.», «30 Prozent» statt «30 %», «2 Meter» statt «2 m», «das heisst» statt «d.h.».
- Vermeide das stumme «e» am Wortende, wenn es nicht unbedingt notwendig ist. Zum Beispiel: «des Fahrzeugs» statt «des Fahrzeuges».
- Verwende immer französische Anführungszeichen (« ») anstelle von deutschen Anführungszeichen („ “).
- Gliedere Telefonnummern mit vier Leerzeichen. Z.B. 044 123 45 67. Den alten Stil mit Schrägstrich (044/123 45 67) und die Vorwahl-Null in Klammern verwendest du NIE.
- Formatiere Datumsangaben immer so: 1. Januar 2022, 15. Februar 2022.
- Jahreszahlen schreibst du immer vierstellig aus: 2022, 2025-2030.
- Formatiere Zeitangaben immer «Stunden Punkt Minuten Uhr». Verwende keinen Doppelpunkt, um Stunden von Minuten zu trennen. Ergänze immer .00 bei vollen Stunden. Beispiele: 9.25 Uhr (NICHT 9:30), 10.30 Uhr (NICHT 10:00), 14.00 Uhr (NICHT 14 Uhr), 15.45 Uhr, 18.00 Uhr, 20.15 Uhr, 22.30 Uhr.
- Zahlen bis 12 schreibst du aus. Ab 13 verwendest du Ziffern.
- Fristen, Geldbeträge und physikalische Grössen schreibst du immer in Ziffern.
- Zahlen, die zusammengehören, schreibst du immer in Ziffern. Beispiel: 5-10, 20 oder 30.
- Grosse Zahlen ab 5 Stellen gliederst du in Dreiergruppen mit Leerzeichen. Beispiel: 1 000 000.
- Achtung: Identifikationszahlen übernimmst du 1:1. Beispiel: Stammnummer 123.456.789, AHV-Nummer 756.1234.5678.90, Konto 01-100101-9.
- Verwende das Komma, dass das deutsche Dezimalzeichen ist. Überflüssige Nullen nach dem Komma schreibst du nicht. Beispiel: 5,5 Millionen, 3,75 Prozent, 1,5 Kilometer, 2,25 Stunden.
- Vor Franken-Rappen-Beträgen schreibst du immer «CHF». Nur nach ganzen Franken-Beträgen darfst du «Franken» schreiben. Bei Franken- Rappen-Beträgen setzt du einen Punkt als Dezimalzeichen. Anstatt des Null-Rappen-Strichs verwendest du «.00» oder lässt die Dezimalstellen weg. Z.B. 20 Franken, CHF 20, CHF 2.00, CHF 12.50, aber CHF 45,2 Millionen, EUR 14,90.
- Die Anrede mit «Sie» schreibst du immer gross. Beispiel: «Sie haben».
""".strip()


RULES_LS = """
- Schreibe wichtiges zuerst: Beginne den Text mit den wichtigsten Informationen, so dass diese sofort klar werden.
- Verwende einfache, kurze, häufig gebräuchliche Wörter.
- Löse zusammengesetzte Wörter auf und formuliere sie neu.
- Wenn es wichtige Gründe gibt, ein zusammengesetztes Wort nicht aufzulösen, trenne das zusammengesetzte Wort mit einem Bindestrich. Beginne dann jedes Wort mit einem Grossbuchstaben. Beispiele: «Auto-Service», «Gegen-Argument», «Kinder-Betreuung», «Volks-Abstimmung».
- Vermeide Fremdwörter. Wähle stattdessen einfache, allgemein bekannte Wörter. Erkläre Fremdwörter, wenn sie unvermeidbar sind.
- Vermeide Fachbegriffe. Wähle stattdessen einfache, allgemein bekannte Wörter. Erkläre Fachbegriffe, wenn sie unvermeidbar sind.
- Vermeide bildliche Sprache. Verwende keine Metaphern oder Redewendungen. Schreibe stattdessen klar und direkt.
- Schreibe kurze Sätze mit optimal 8 und höchstens 12 Wörtern.
- Du darfst Relativsätze mit «der», «die», «das» verwenden.
- Löse Nebensätze nach folgenden Regeln auf:
    - Kausalsätze (weil, da): Löse Kausalsätze als zwei Hauptsätze mit «deshalb» auf.
    - Konditionalsätze (wenn, falls): Löse Konditionalsätze als zwei Hauptsätze mit «vielleicht» auf.
    - Finalsätze (damit, dass): Löse Finalsätze als zwei Hauptsätze mit «deshalb» auf.
    - Konzessivsätze (obwohl, obgleich, wenngleich, auch wenn): Löse Konzessivsätze als zwei Hauptsätze mit «trotzdem» auf.
    - Temporalsätze (als, während, bevor, nachdem, sobald, seit): Löse Temporalsätze als einzelne chronologische Sätze auf. Wenn es passt, verknüpfe diese mit «dann».
    - Adversativsätze (aber, doch, jedoch, allerdings, sondern, allein): Löse Adversativsätze als zwei Hauptsätze mit «aber» auf.
    - Modalsätze (indem, dadurch dass): Löse Modalsätze als zwei Hauptsätze auf. Z.B. Alltagssprache: Er lernt besser, indem er regelmässig übt. Leichte Sprache: Er lernt besser. Er übt regelmässig.
    - Konsekutivsätze (so dass, sodass): Löse Konsekutivsätze als zwei Hauptsätze auf. Z.B. Alltagssprache: Er ist krank, sodass er nicht arbeiten konnte. Leichte Sprache: Er ist krank. Er konnte nicht arbeiten.
    - Relativsätze mit «welcher», «welche», «welches»: Löse solche Relativsätze als zwei Hauptsätze auf. Z.B. Alltagssprache: Das Auto, welches rot ist, steht vor dem Haus. Leichte Sprache: Das Auto ist rot. Das Auto steht vor dem Haus.
    - Ob-Sätze: Schreibe Ob-Sätze als zwei Hauptsätze. Z.B. Alltagssprache: Er fragt, ob es schönes Wetter wird. Leichte Sprache: Er fragt: Wird es schönes Wetter?
- Verwende aktive Sprache anstelle von Passiv.
- Benutze den Genitiv nur in einfachen Fällen. Verwende stattdessen die Präposition "von" und den Dativ.
- Vermeide das stumme «e» am Wortende, wenn es nicht unbedingt notwendig ist. Zum Beispiel: «des Fahrzeugs» statt «des Fahrzeuges».
- Bevorzuge die Vorgegenwart (Perfekt). Vermeide die Vergangenheitsform (Präteritum), wenn möglich. Verwende das Präteritum nur bei den Hilfsverben (sein, haben, werden) und bei Modalverben (können, müssen, sollen, wollen, mögen, dürfen).
- Benenne Gleiches immer gleich. Verwende für denselben Begriff, Gegenstand oder Sachverhalt immer dieselbe Bezeichnung. Wiederholungen von Begriffen sind in Texten in Leichter Sprache normal.
- Vermeide Pronomen. Verwende Pronomen nur, wenn der Bezug ganz klar ist. Sonst wiederhole das Nomen.
- Formuliere grundsätzlich positiv und bejahend. Vermeide Verneinungen ganz.
- Verwende IMMER die Satzstellung Subjekt-Prädikat-Objekt.
- Vermeide Substantivierungen. Verwende stattdessen Verben und Adjektive.
- Achte auf die sprachliche Gleichbehandlung von Mann und Frau. Verwende immer beide Geschlechter oder schreibe geschlechtsneutral.
- Vermeide Abkürzungen grundsätzlich. Schreibe stattdessen die Wörter aus. Z.B. «10 Millionen» statt «10 Mio.», «200 Kilometer pro Stunde» statt «200 km/h», «zum Beispiel» statt «z.B.», «30 Prozent» statt «30 %», «2 Meter» statt «2 m», «das heisst» statt «d.h.». Je nach Kontext kann es aber sinnvoll sein, eine Abkürzung einzuführen. Schreibe dann den Begriff einmal aus, erkläre ihn, führe die Abkürzung ein und verwende sie dann konsequent.
- Schreibe die Abkürzungen «usw.», «z.B.», «etc.» aus. Also zum Beispiel «und so weiter», «zum Beispiel», «etcetera».
- Formatiere Zeitangaben immer «Stunden Punkt Minuten Uhr». Verwende keinen Doppelpunkt, um Stunden von Minuten zu trennen. Ergänze immer .00 bei vollen Stunden. Beispiele: 9.25 Uhr (NICHT 9:30), 10.30 Uhr (NICHT 10:00), 14.00 Uhr (NICHT 14 Uhr), 15.45 Uhr, 18.00 Uhr, 20.15 Uhr, 22.30 Uhr.
- Formatiere Datumsangaben immer so: 1. Januar 2022, 15. Februar 2022.
- Jahreszahlen schreibst du immer vierstellig aus: 2022, 2025-2030.
- Verwende immer französische Anführungszeichen (« ») anstelle von deutschen Anführungszeichen („ “).
- Gliedere Telefonnummern mit vier Leerzeichen. Z.B. 044 123 45 67. Den alten Stil mit Schrägstrich (044/123 45 67) und die Vorwahl-Null in Klammern verwendest du NIE.
- Zahlen bis 12 schreibst du aus. Ab 13 verwendest du Ziffern.
- Fristen, Geldbeträge und physikalische Grössen schreibst du immer in Ziffern.
- Zahlen, die zusammengehören, schreibst du immer in Ziffern. Beispiel: 5-10, 20 oder 30.
- Grosse Zahlen ab 5 Stellen gliederst du in Dreiergruppen mit Leerzeichen. Beispiel: 1 000 000.
- Achtung: Identifikationszahlen übernimmst du 1:1. Beispiel: Stammnummer 123.456.789, AHV-Nummer 756.1234.5678.90, Konto 01-100101-9.
- Verwende das Komma, dass das deutsche Dezimalzeichen ist. Überflüssige Nullen nach dem Komma schreibst du nicht. Beispiel: 5 Millionen, 3,75 Prozent, 1,5 Kilometer, 2,25 Stunden.
- Vor Franken-Rappen-Beträgen schreibst du immer «CHF». Nur nach ganzen Franken-Beträgen darfst du «Franken» schreiben. Bei Franken-Rappen-Beträgen setzt du einen Punkt als Dezimalzeichen. Anstatt des Null-Rappen-Strichs verwendest du «.00» oder lässt die Dezimalstellen weg. Z.B. 20 Franken, CHF 20, CHF 2.00, CHF 12.50, aber CHF 45,2 Millionen, EUR 14,90.
- Die Anrede mit «Sie» schreibst du immer gross. Beispiel: «Sie haben».
- Strukturiere den Text. Gliedere in sinnvolle Abschnitte und Absätze. Verwende Titel und Untertitel grosszügig, um den Text zu gliedern. Es kann hilfreich sein, wenn diese als Frage formuliert sind.
- Stelle Aufzählungen als Liste dar.
- Zeilenumbrüche helfen, Sinneinheiten zu bilden und erleichtern das Lesen. Füge deshalb nach Haupt- und Nebensätzen sowie nach sonstigen Sinneinheiten Zeilenumbrüche ein. Eine Sinneinheit soll maximal 8 Zeilen umfassen.
- Eine Textzeile enthält inklusiv Leerzeichen maximal 85 Zeichen.
""".strip()


REWRITE_COMPLETE = """- Achte immer sehr genau darauf, dass ALLE Informationen aus dem schwer verständlichen Text in deinem verständlicheren Text enthalten sind. Kürze niemals Informationen. Wo sinnvoll kannst du zusätzliche Beispiele hinzufügen, um den Text verständlicher zu machen und relevante Inhalte zu konkretisieren."""


REWRITE_CONDENSED = (
    """- Konzentriere dich auf das Wichtigste. Gib die essenziellen Informationen wieder und lass den Rest weg."""
)


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

Formuliere den Text jetzt in Einfache Sprache, Sprachniveau B1 bis A2, um. Schreibe den vereinfachten Text innerhalb von <einfachesprache> Tags.
""".strip()

# Claude template for "Leichte Sprache" (Easy Language)
CLAUDE_TEMPLATE_LS: str = """
Hier ist ein schwer verständlicher Text, den du vollständig in Leichte Sprache, Sprachniveau A2 bis A1, umschreiben sollst:

<schwer-verständlicher-text>
{prompt}
</schwer-verständlicher-text>

Bitte lies den Text sorgfältig durch und schreibe ihn vollständig in Leichte Sprache um.

Beachte dabei folgende Regeln:

{completeness}
{rules}

Formuliere den Text jetzt in Leichte Sprache, Sprachniveau A2 bis A1, um. Schreibe den vereinfachten Text innerhalb von <leichtesprache> Tags.
""".strip()

# Claude template for analyzing text for "Einfache Sprache" compliance
CLAUDE_TEMPLATE_ANALYSIS_ES: str = """
Hier ist ein schwer verständlicher Text, den du genau analysieren sollst:

<schwer-verständlicher-text>
{prompt}
</schwer-verständlicher-text>

Analysiere den schwer verständlichen Text Satz für Satz. Beschreibe genau und detailliert, was sprachlich nicht gut bei jedem Satz ist. Analysiere was ich tun müsste, damit der Text zu Einfache Sprache (B1 bis A2) wird. Gib klare Hinweise, wie ich den Text besser verständlich machen kann. Gehe bei deiner Analyse Schritt für Schritt vor.

1. Wiederhole den Satz.
2. Analysiere den Satz auf seine Verständlichkeit. Was muss ich tun, damit der Satz verständlicher wird? Wie kann ich den Satz in Einfacher Sprache besser formulieren?
3. Mache einen Vorschlag für einen vereinfachten Satz.

Befolge diesen Ablauf von Anfang bis Ende, auch wenn der schwer verständliche Text sehr lang ist.

Die Regeln für Einfache Sprache sind diese hier:

{rules}

Schreibe jetzt deine Analyse und gib diese innerhalb von <einfachesprache> Tags aus.
""".strip()

# Claude template for analyzing text for "Leichte Sprache" compliance
CLAUDE_TEMPLATE_ANALYSIS_LS: str = """
Hier ist ein schwer verständlicher Text, den du genau analysieren sollst:

<schwer-verständlicher-text>
{prompt}
</schwer-verständlicher-text>

Analysiere den schwer verständlichen Text Satz für Satz. Beschreibe genau und detailliert, was sprachlich nicht gut bei jedem Satz ist. Analysiere was ich tun müsste, damit der Text zu Leichte Sprache (A2, A1) wird. Gib klare Hinweise, wie ich den Text besser verständlich machen kann. Gehe bei deiner Analyse Schritt für Schritt vor.

1. Wiederhole den Satz.
2. Analysiere den Satz auf seine Verständlichkeit. Was muss ich tun, damit der Satz verständlicher wird? Wie kann ich den Satz in Leichte Sprache besser formulieren?
3. Mache einen Vorschlag für einen vereinfachten Satz.

Befolge diesen Ablauf von Anfang bis Ende, auch wenn der schwer verständliche Text sehr lang ist.

Die Regeln für Leichte Sprache sind diese hier:

{rules}

Schreibe jetzt deine Analyse und gib diese innerhalb von <leichtesprache> Tags aus.
""".strip()


# =============================================================================
# OPENAI TEMPLATES
# =============================================================================

# OpenAI template for "Einfache Sprache" (Simple Language)
OPENAI_TEMPLATE_ES: str = """
Du bekommst einen schwer verständlichen Text, den du vollständig in Einfache Sprache auf Sprachniveau B1 bis A2 umschreiben sollst.

Beachte dabei folgende Regeln:

{completeness}
{rules}

Schreibe den vereinfachten Text innerhalb von <einfachesprache> Tags. Gib nur Text aus, keine Markdown-Formatierung, kein HTML.

Hier ist der schwer verständliche Text:

--------------------------------------------------------------------------------

{prompt}
""".strip()

# OpenAI template for "Leichte Sprache" (Easy Language)
OPENAI_TEMPLATE_LS: str = """
Du bekommst einen schwer verständlichen Text, den du vollständig in Leichte Sprache auf Sprachniveau A2 bis A1 umschreiben sollst.

Beachte dabei folgende Regeln:

{completeness}
{rules}

Schreibe den vereinfachten Text innerhalb von <leichtesprache> Tags. Gib nur Text aus, keine Markdown-Formatierung, kein HTML.

Hier ist der schwer verständliche Text:

--------------------------------------------------------------------------------

{prompt}
""".strip()

# OpenAI template for analyzing text for "Einfache Sprache" compliance
OPENAI_TEMPLATE_ANALYSIS_ES: str = """
Du bekommst einen schwer verständlichen Text, den du genau analysieren sollst.

Analysiere den schwer verständlichen Text Satz für Satz. Beschreibe genau und detailliert, was sprachlich nicht gut bei jedem Satz ist. Analysiere was ich tun müsste, damit der Text zu Einfache Sprache (B1 bis A2) wird. Gib klare Hinweise, wie ich den Text besser verständlich machen kann. Gehe bei deiner Analyse Schritt für Schritt vor.

1. Wiederhole den Satz.
2. Analysiere den Satz auf seine Verständlichkeit. Was muss ich tun, damit der Satz verständlicher wird? Wie kann ich den Satz in Einfache Sprache formulieren?
3. Mache einen Vorschlag für einen vereinfachten Satz.

Befolge diesen Ablauf von Anfang bis Ende, auch wenn der schwer verständliche Text sehr lang ist.

Die Regeln für Einfache Sprache sind diese hier:

{rules}

Schreibe deine Analyse innerhalb von <einfachesprache> Tags. Gib nur Text aus, keine Markdown-Formatierung, kein HTML.

Hier ist der schwer verständliche Text:

--------------------------------------------------------------------------------

{prompt}
""".strip()

# OpenAI template for analyzing text for "Leichte Sprache" compliance
OPENAI_TEMPLATE_ANALYSIS_LS: str = """
Du bekommst einen schwer verständlichen Text, den du genau analysieren sollst.

Analysiere den schwer verständlichen Text Satz für Satz. Beschreibe genau und detailliert, was sprachlich nicht gut bei jedem Satz ist. Analysiere was ich tun müsste, damit der Text zu Leichte Sprache (A2 bis A1) wird. Gib klare Hinweise, wie ich den Text besser verständlich machen kann. Gehe bei deiner Analyse Schritt für Schritt vor.

1. Wiederhole den Satz.
2. Analysiere den Satz auf seine Verständlichkeit. Was muss ich tun, damit der Satz verständlicher wird? Wie kann ich den Satz in Leichte Sprache formulieren?
3. Mache einen Vorschlag für einen vereinfachten Satz.

Befolge diesen Ablauf von Anfang bis Ende, auch wenn der schwer verständliche Text sehr lang ist.

Die Regeln für Leichte Sprache sind diese hier:

{rules}

Schreibe deine Analyse innerhalb von <leichtesprache> Tags. Gib nur Text aus, keine Markdown-Formatierung, kein HTML.

Hier ist der schwer verständliche Text:

--------------------------------------------------------------------------------

{prompt}
""".strip()


# =============================================================================
# TEMPLATE HELPER FUNCTIONS
# =============================================================================


def get_es_template(provider: str, analysis: bool = False) -> str:
    """Get the appropriate template for Einfache Sprache based on provider and type.

    Args:
        provider: The LLM provider ('claude' or 'openai')
        analysis: Whether to get analysis template (True) or rewrite template (False)

    Returns:
        The appropriate template string

    Raises:
        ValueError: If provider is not supported
    """
    if provider.lower() == "claude":
        return CLAUDE_TEMPLATE_ANALYSIS_ES if analysis else CLAUDE_TEMPLATE_ES
    elif provider.lower() == "openai":
        return OPENAI_TEMPLATE_ANALYSIS_ES if analysis else OPENAI_TEMPLATE_ES
    else:
        raise ValueError(f"Unsupported provider: {provider}")


def get_ls_template(provider: str, analysis: bool = False) -> str:
    """Get the appropriate template for Leichte Sprache based on provider and type.

    Args:
        provider: The LLM provider ('claude' or 'openai')
        analysis: Whether to get analysis template (True) or rewrite template (False)

    Returns:
        The appropriate template string

    Raises:
        ValueError: If provider is not supported
    """
    if provider.lower() == "claude":
        return CLAUDE_TEMPLATE_ANALYSIS_LS if analysis else CLAUDE_TEMPLATE_LS
    elif provider.lower() == "openai":
        return OPENAI_TEMPLATE_ANALYSIS_LS if analysis else OPENAI_TEMPLATE_LS
    else:
        raise ValueError(f"Unsupported provider: {provider}")


def get_completeness_instruction(complete: bool = True) -> str:
    """Get the appropriate completeness instruction.

    Args:
        complete: Whether to preserve all information (True) or condense (False)

    Returns:
        The appropriate completeness instruction string
    """
    return REWRITE_COMPLETE if complete else REWRITE_CONDENSED


def get_rules(language_type: str) -> str:
    """Get the rules for the specified language type.

    Args:
        language_type: Either 'es' for Einfache Sprache or 'ls' for Leichte Sprache

    Returns:
        The appropriate rules string

    Raises:
        ValueError: If language_type is not supported
    """
    if language_type.lower() == "es":
        return RULES_ES
    elif language_type.lower() == "ls":
        return RULES_LS
    else:
        raise ValueError(f"Unsupported language type: {language_type}")


def get_system_message(language_type: str) -> str:
    """Get the system message for the specified language type.

    Args:
        language_type: Either 'es' for Einfache Sprache or 'ls' for Leichte Sprache

    Returns:
        The appropriate system message string

    Raises:
        ValueError: If language_type is not supported
    """
    if language_type.lower() == "es":
        return SYSTEM_MESSAGE_ES
    elif language_type.lower() == "ls":
        return SYSTEM_MESSAGE_LS
    else:
        raise ValueError(f"Unsupported language type: {language_type}")

"""Reconciled German style block for the simplification pipeline (Basel-Stadt).

.. warning::

   **HUMAN REVIEW REQUIRED BEFORE MERGE.**

   ``SIMPLIFY_STYLE_DE`` is prompt content, and prompt content is a systematic-error
   surface: every sentence in it is applied to every German text the tool rewrites. It was
   composed by hand from the sources listed below, but it has **not** been signed off by a
   Basel-Stadt language reviewer. Do not ship it to users before that review.

What this module is
-------------------

One hand-curated, deduplicated German style constant for the ``de`` branch of the
simplification prompt (``utils/simplify_prompt.py``). It is the Python equivalent of
blokkli's skill ``streamTemplates`` seam: static, reviewable text — **not** rules injected
at runtime and **not** rules synthesised offline by an LLM.
See ``docs/simplify_redesign.md`` §5.2.

Where each section comes from
-----------------------------

======================================  ==========================================================
Section                                 Sources
======================================  ==========================================================
1. Ton und Anrede                       ``BASEL_STADT_HOUSE_STYLE`` 1;
                                        ``merkblatt_behoerdenbriefe``: «Persönliche Anrede mit
                                        ‹Sie›», «Persönlicher Stil mit ‹ich› und ‹wir›»,
                                        «Respektvoller Ton auf Augenhöhe», «Keine Floskeln»,
                                        «Kein Amtsjargon»; ``RULES_ES`` («kein Behördendeutsch»)
2. Sätze                                ``merkblatt_behoerdenbriefe``: «Kurze, einfach gebaute
                                        Sätze», «Ein Gedanke pro Satz»;
                                        ``BASEL_STADT_HOUSE_STYLE`` 1; ``RULES_ES``
3. Aufbau                               ``merkblatt_behoerdenbriefe``: «Roter Faden im Aufbau»;
                                        ``RULES_ES``
4. Wörter                               ``RULES_ES``; ``BASEL_STADT_HOUSE_STYLE`` 4;
                                        ``bundeskanzlei``: «Unnötige Anglizismen durch deutsches
                                        Wort ersetzen», «Etablierte Anglizismen beibehalten»,
                                        «Unklare oder fachsprachliche Anglizismen erklären»,
                                        «Einheitliche Schreibvariante im selben Text»
5. Geschlechtergerechte Sprache         ``BASEL_STADT_HOUSE_STYLE`` 2; ``bundeskanzlei``: «Kein
                                        generisches Maskulinum», «Paarform mit beiden
                                        Geschlechtern», «Verbotene Genderschreibweisen»,
                                        «Geschlechtsneutrale Formen zulässig», «Konsistente
                                        Reihenfolge der Paarform», «Konjunktion oder/und in
                                        Paarformen», «Keine Paarform im ersten Teil eines
                                        Kompositums», «Keine Sparschreibung im fortlaufenden Text»
6. Rechtschreibung und Typografie       ``BASEL_STADT_HOUSE_STYLE`` 3; ``bundeskanzlei``:
                                        «Doppel-s statt Eszett (ß)», «Guillemets als
                                        Anführungszeichen verwenden», «Halbe Anführungszeichen für
                                        verschachtelte Zitate», «Sehr lange Zusammensetzungen mit
                                        Bindestrich gliedern»; ``RULES_ES``
7. Zahlen, Daten, Zeiten, Beträge       ``bundeskanzlei``: «Kurze Zahlen im Fliesstext
                                        ausschreiben», «Mehrere Zahlen im gleichen Zusammenhang in
                                        Ziffern», «Masse, Gewichte und Währungen mit abgekürzter
                                        Einheit in Ziffern», «Grosse Zahlen in Dreiergruppen mit
                                        Festabstand gliedern», «Uhrzeit mit Punkt in der
                                        24-Stunden-Zählung», «Volle Stunden ohne Minutenangabe»,
                                        «Datum im Fliesstext mit ausgeschriebenem Monat»,
                                        «Jahreszahlen vierstellig schreiben», «Geldbeträge mit
                                        Währungseinheit vor dem Betrag», «Franken und Rappen mit
                                        Punkt, fehlende Rappen mit Gedankenstrich»,
                                        «Mehrgliedrige Abkürzungen mit Festabstand», «Inländische
                                        Telefonnummern in Zweier- und Dreiergruppen»;
                                        ``RULES_ES``
8. Fakten                               ``BASEL_STADT_HOUSE_STYLE`` 5; ``RULES_ES``
                                        (Identifikationszahlen); ``REWRITE_COMPLETE``
======================================  ==========================================================

Deduplication note: «kurze Sätze im Aktiv, ein Gedanke pro Satz» appears in all three
sources, «Amtsdeutsch/Floskeln vermeiden» in two, «Fachbegriffe erklären» in two, and the
gendering ban list in two. Each appears exactly once below.

Maintenance
-----------

This constant is deliberately **standalone text**, not assembled from ``RULES_ES`` at
import time, so that a reviewer can read the one artefact that reaches the model. The
price is drift: when ``utils/easy_language.py`` ``RULES_ES`` or
``utils/house_style.py`` change, this block must be updated in the same commit, and
``docs/simplify_rules_audit.md`` re-checked.
"""
# ruff: noqa: E501  # Line too long - German language rules and prompts need to be preserved exactly

from __future__ import annotations

SIMPLIFY_STYLE_DE: str = """
# SPRACHREGELN FÜR EINFACHE SPRACHE (KANTON BASEL-STADT)

## 1. Ton und Anrede
- Sprich die Leserin oder den Leser direkt mit «Sie» an. «Sie», «Ihr» und «Ihnen» schreibst du immer gross.
- Schreibe persönlich: «wir» für die Verwaltung, «Sie» für die angeschriebene Person. Verstecke dich nicht hinter «die Behörde», «es wird» oder anderen unpersönlichen Formen.
- Schreibe respektvoll und auf Augenhöhe, nie von oben herab, nie drohend oder misstrauisch.
- Bitte und danke dort, wo es angebracht ist. Formuliere Aufforderungen nicht rein befehlend.
- Vermeide Amtsdeutsch, Kanzleistil und Floskeln. Statt «Zur Beantwortung steht Ihnen Herr XY zur Verfügung» schreibst du «Rufen Sie uns an, wenn Sie Fragen haben». Statt «in Kenntnis setzen» schreibst du «mitteilen», statt «in Abzug bringen» schreibst du «abziehen».
- Vermeide veraltete Begriffe und komplizierte Konstruktionen. Schreibe einfach, direkt und klar.

## 2. Sätze
- Schreibe kurze Sätze mit höchstens 12 Wörtern.
- Beschränke dich auf eine Aussage, einen Gedanken pro Satz.
- Entflechte Schachtelsätze Satz für Satz. Aus einem langen Satz dürfen mehrere kurze werden.
- Verwende aktive Sprache anstelle von Passiv.
- Formuliere grundsätzlich positiv und bejahend.
- Vermeide Substantivierungen. Verwende stattdessen Verben und Adjektive.
- Vermeide Adjektive und Adverbien, wenn sie nicht unbedingt notwendig sind.

## 3. Aufbau
- Beginne mit dem, was die Leserin oder der Leser unbedingt wissen muss. Die Kernbotschaft steht vorne.
- Strukturiere den Text übersichtlich mit kurzen Absätzen und folge einem roten Faden.
- Stelle Aufzählungen als Liste dar.
- Vermeide Füllwörter und unnötige Wiederholungen. Lass Überflüssiges weg.
- Muss die Leserin oder der Leser etwas tun, sagst du klar: was, bis wann, an welche Stelle und was passiert, wenn es unterbleibt.

## 4. Wörter
- Verwende einfache, kurze, häufig gebräuchliche Wörter.
- Wenn zwei Wörter dasselbe bedeuten, verwende das kürzere und einfachere Wort.
- Erkläre Fachbegriffe und Fremdwörter bei der ersten Verwendung.
- Benenne Gleiches immer gleich. Verwende für denselben Begriff, Gegenstand oder Sachverhalt immer dieselbe Bezeichnung. Wiederholungen von Begriffen sind in Einfacher Sprache normal.
- Wo mehrere Schreibvarianten zulässig sind, verwendest du im ganzen Text durchgehend dieselbe.
- Ersetze unnötige Anglizismen durch das deutsche Wort: «Sitzung» statt «Meeting», «Veranstaltung» statt «Event», «Sicherungskopie» statt «Back-up».
- Etablierte Anglizismen behältst du bei: «E-Mail», «Computer», «Leasing». Erfinde keine künstlichen deutschen Ersatzwörter.
- Fachsprachliche oder neue Anglizismen erklärst du bei der ersten Nennung oder ersetzt sie.
- Verwende keinen Jugend- oder Werbeslang.

## 5. Geschlechtergerechte Sprache
- Verwende nie die alleinige männliche Form für Personen unbekannten oder gemischten Geschlechts.
- Verwende Paarformen («Bürgerinnen und Bürger», «die Mitarbeiterin oder der Mitarbeiter») oder geschlechtsneutrale Formen («die Stimmberechtigten», «die Fachperson», «die Belegschaft»).
- Verwende NIE Gendersternchen, Doppelpunkt, Unterstrich, Mediopunkt, Binnen-I, Klammerform oder Schrägstrich-Sparschreibung: nicht «Bürger*innen», «Bürger:innen», «Bürger_innen», «Bürger·innen», «BürgerInnen», «Bürger(innen)», «Bürger/-innen».
- Verwende keine Paarform im ersten Teil eines zusammengesetzten Wortes: «Kundendienst», nicht «Kundinnen- und Kundendienst».
- Behalte die einmal gewählte Reihenfolge der Paarform im ganzen Text bei.
- Verbinde die Paarform in der Einzahl mit «oder», in der Mehrzahl mit «und», nie mit «beziehungsweise».
- Juristische Personen und Organisationseinheiten bezeichnest du mit nur einer Form.

## 6. Rechtschreibung und Typografie
- Verwende Schweizer Rechtschreibung: immer «ss», nie «ß».
- Verwende immer französische Anführungszeichen (« ») anstelle von deutschen Anführungszeichen („ “). Für ein Zitat innerhalb eines Zitats verwendest du die halben Guillemets (‹ ›).
- Besteht eine Zusammensetzung aus vier oder mehr Sinneinheiten, gliederst du sie mit einem Bindestrich, ohne eine Sinneinheit auseinanderzureissen: «Motorfahrzeug-Ausweispflicht», «Rheinschifffahrtspolizei-Verordnung». Kurze Zusammensetzungen aus zwei oder drei Teilen schreibst du ohne Bindestrich.
- Vermeide Abkürzungen für Wörter. Schreibe sie aus: «zum Beispiel» statt «z. B.», «das heisst» statt «d. h.», «und so weiter» statt «usw.», «10 Millionen» statt «10 Mio.». Verwendest du eine mehrgliedrige Abkürzung ausnahmsweise doch, setzt du ein Leerzeichen zwischen ihre Bestandteile: «z. B.», «d. h.».
- Gliedere inländische Telefonnummern so: die Vorwahl als Dreierblock mit führender Null, die übrigen Ziffern in Zweierblöcken, getrennt durch Leerzeichen: 044 123 45 67. Schrägstriche und Klammern um die Vorwahl verwendest du NIE.

## 7. Zahlen, Daten, Zeiten und Beträge
- Zahlen bis zwölf schreibst du aus, ebenso runde Zahlwörter wie zwanzig, hundert, tausend. Ab 13 verwendest du Ziffern.
- Fristen, Geldbeträge und physikalische Grössen schreibst du immer in Ziffern.
- Zahlen, die zusammengehören oder einander gegenübergestellt werden, schreibst du in Ziffern: «Die Frist beträgt 7 Tage, bei Verträgen 14 Tage».
- Prozentangaben schreibst du als Ziffer direkt gefolgt vom Prozentzeichen, ohne Leerzeichen: «30%». Mass- und Gewichtsangaben schreibst du als Ziffer mit einem Leerzeichen vor der Einheit: «5 t», «10 m», «2 Tonnen». Für gebräuchliche Einheiten wie Meter (m), Kilometer (km), Gramm (g), Kilogramm (kg), Liter (l) oder Milliliter (ml) verwendest du die Abkürzung; alle anderen Einheiten schreibst du aus.
- Grosse Zahlen ab 5 Stellen gliederst du in Dreiergruppen mit Leerzeichen: 1 000 000. Vierstellige Zahlen bleiben ungegliedert. Apostroph, Punkt und Komma verwendest du dafür NIE.
- Ausserhalb von Geldbeträgen ist das Komma das deutsche Dezimalzeichen. Überflüssige Nullen nach dem Komma schreibst du nicht: 5,5 Millionen, 3,75 %, 2,25 Stunden.
- Bei einem genau bezifferten Geldbetrag verwendest du als Währungseinheit «Fr.» und schreibst sie mit Leerzeichen VOR den Betrag: Fr. 327.65, Fr. 12.50, Fr. 40.50. Die Einheit steht nie hinter dem Betrag (NICHT 40.50 Fr.). Im Fliesstext ohne genaue Ziffer schreibst du «Franken» aus: 20 Franken, 50 000 Franken; ein Beispiel: aus «40.50 Franken» wird «Fr. 40.50» (NICHT 40.50 Franken). Andere Währungen behandelst du gleich: EUR 14.90.
- Franken und Rappen trennst du mit einem Punkt, nie mit einem Komma. Fehlen die Rappen, setzt du an ihrer Stelle einen Gedankenstrich: Fr. 20.– (NICHT Fr. 20.00, NICHT Fr. 20,–). Bei grossen, gerundeten Beträgen gilt wieder das Dezimalkomma: Fr. 45,2 Millionen.
- Formatiere Datumsangaben immer so: 1. Januar 2022, 15. Februar 2022. Den Monatsnamen schreibst du immer aus, nie als Ziffer.
- Jahreszahlen schreibst du immer vierstellig aus: 2022, 2025-2030.
- Formatiere Zeitangaben in der 24-Stunden-Zählung und trenne Stunden und Minuten mit einem Punkt, nie mit einem Doppelpunkt: 9.25 Uhr, 15.45 Uhr, 20.15 Uhr. Volle Stunden schreibst du ohne Minutenangabe: 14 Uhr (NICHT 14.00 Uhr).

## 8. Fakten
- Übernimm alle Fakten – Daten, Fristen, Namen, Beträge, Bedingungen, Pflichten – exakt und unverändert.
- Identifikationszahlen übernimmst du 1:1: Stammnummer 123.456.789, AHV-Nummer 756.1234.5678.90, Konto 01-100101-9.
- Erfinde nichts dazu. Schreibe nur, was im Ausgangstext steht.
""".strip()

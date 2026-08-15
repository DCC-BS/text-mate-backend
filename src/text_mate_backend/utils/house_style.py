# Hausstil der Verwaltung Kanton Basel-Stadt.
# Abgeleitet aus den amtlichen Leitfäden in assets/docs/
# (Merkblatt Behördenbriefe, Rechtschreibleitfaden, Leitfaden geschlechtergerechte
# Sprache, Empfehlungen Anglizismen) und abgestimmt mit utils/simplify_style.py.
# Wird von den Brief-, E-Mail-, Präsentations- und Berichts-Prompts wiederverwendet.

# ruff: noqa: E501  # Line too long - German language rules and prompts need to be preserved exactly

BASEL_STADT_HOUSE_STYLE = """
# HAUSSTIL KANTON BASEL-STADT
Beachte beim Schreiben immer die folgenden Regeln der Verwaltung Kanton Basel-Stadt.
Wichtige Sprachregel: Diese Richtlinien gelten primär für deutschsprachige Texte. Bei Texten in anderen Sprachen (z. B. Englisch, Französisch, Italienisch) wende die allgemeinen Grundsätze (wie Klarheit, Direktheit, bürgernaher Ton und Faktentreue) sinngemäss in der Originalsprache an. Behalte zwingend die Sprache des Ausgangstextes bei und übersetze ihn keinesfalls ins Deutsche!

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
